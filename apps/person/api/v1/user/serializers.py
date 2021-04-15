from django.conf import settings
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import EmailValidator

from rest_framework import serializers, status as response_status
from rest_framework.exceptions import NotAcceptable, NotAuthenticated

from utils.generals import create_unique_id, get_model
from apps.person.api.serializers import ModelSerializerWithClean
from apps.person.api.validator import (
    EmailDuplicateValidator,
    MsisdnDuplicateValidator,
    MsisdnNumberValidator
)

from ..profile.serializers import ProfileSerializer

User = get_model('person', 'User')
VerifyCode = get_model('person', 'VerifyCode')


class DynamicFields(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)
        context = kwargs.get('context', dict())
        request = context.get('request', None)

        # Instantiate the superclass normally
        super(DynamicFields, self).__init__(*args, **kwargs)

        # Fields at specific request
        if request.method == 'PATCH':
            # Only this fields allowed update
            fields = ('username', 'first_name', 'email', 'msisdn',)

        if fields is not None and fields != '__all__':
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class BaseUserSerializer(DynamicFields, serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='person_api:user-detail',
                                               lookup_field='uuid', read_only=True)
    name = serializers.CharField(read_only=True)
    profile = ProfileSerializer(many=False, read_only=True)

    class Meta:
        model = User
        exclude = ('id', 'user_permissions', 'groups', 'date_joined',
                   'is_superuser', 'last_login', 'is_staff',)
        extra_kwargs = {
            'password': {
                'write_only': True,
                'min_length': 6
            },
            'first_name': {
                'required': True
            },
            'username': {
                'required': True,
                'min_length': 4,
                'max_length': 15
            },
            'email': {
                'required': False,
                'validators': [EmailValidator()]
            },
            'msisdn': {
                'required': False,
                'validators': [MsisdnNumberValidator()],
                'min_length': 8,
                'max_length': 14
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._verifycode_obj = VerifyCode.objects.none()
        self._verifycode_queryset = VerifyCode.objects.select_for_update()


class ValidateUserSerializer(object):
    def validate_email(self, value):
        error_message = _("Email not verified")

        # not update yet
        if self.instance and self.instance.email == value:
            return value

        # check email verified
        if settings.STRICT_EMAIL_VERIFIED:
            request = self.context.get('request')
            verifycode_token = request.session.get(
                'verifycode_token') if request else None

            with transaction.atomic():
                try:
                    self._verifycode_obj = self._verifycode_queryset \
                        .verified_unused(email=value, token=verifycode_token,
                                         challenge=VerifyCode.ChallengeType.VALIDATE_EMAIL)
                except ObjectDoesNotExist:
                    raise NotAuthenticated(detail=error_message)
        return value

    def validate_msisdn(self, value):
        error_message = _("Msisdn not verified")

        # not update yet
        if self.instance and self.instance.msisdn == value:
            return value

        # check msisdn verified
        if settings.STRICT_MSISDN_VERIFIED:
            request = self.context.get('request')
            verifycode_token = request.session.get(
                'verifycode_token') if request else None

            with transaction.atomic():
                try:
                    self._verifycode_obj = self._verifycode_queryset \
                        .verified_unused(msisdn=value, token=verifycode_token,
                                         challenge=VerifyCode.ChallengeType.VALIDATE_MSISDN)
                except ObjectDoesNotExist:
                    raise NotAuthenticated(detail=error_message)
        return value

    def validate_password(self, value):
        password = self.initial_data.get('password')
        retype_password = self.initial_data.get('retype_password')
        if password != retype_password:
            raise serializers.ValidationError(detail=_("Password tidak sama"))
        return value


class CreateUserSerializer(BaseUserSerializer):
    def validate(self, data):
        print(data)
        validated_data = super().validate(data)
        print(validated_data)
        ModelClass = self.Meta.model
        instance = ModelClass._default_manager.create(**validated_data)

        raise serializers.ValidationError(detail=_("Password tidak sama"))
        # can't use both email and msisdn
        if 'email' in data and 'msisdn' in data:
            raise serializers.ValidationError(
                detail=_("Can't use both email and msisdn"))
        return validated_data

    def get_extra_kwargs(self):
        kwargs = super().get_extra_kwargs()

        if settings.STRICT_MSISDN:
            kwargs['msisdn']['required'] = True

            # check duplicate
            if settings.STRICT_MSISDN_DUPLICATE:
                kwargs['msisdn']['validators'].append(
                    MsisdnDuplicateValidator())

        if settings.STRICT_EMAIL:
            kwargs['email']['required'] = True

            # check duplicate
            if settings.STRICT_EMAIL_DUPLICATE:
                kwargs['email']['validators'].append(EmailDuplicateValidator())

        # mark username not-required if first_name exist
        if 'first_name' in self.initial_data:
            kwargs['username']['required'] = False

        # mark first_name not-required if username exist
        if 'username' in self.initial_data:
            kwargs['first_name']['required'] = False

        return kwargs

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)

        # use username as first_name
        if 'first_name' not in data:
            ret['first_name'] = data.get('username')

        # create username from first_name
        if 'username' not in data:
            ret['username'] = '{}{}'.format(
                slugify(data.get('first_name')), create_unique_id(2))
        return ret

    @transaction.atomic
    def create(self, validated_data):
        try:
            instance = get_user_model().objects.create_user(**validated_data)
        except (IntegrityError, TypeError, ValueError) as e:
            raise ValidationError(str(e))

        # mark verifycode as used
        if self._verifycode_obj:
            self._verifycode_obj.mark_used()

            # mark verified
            if self._verifycode_obj.email is not None:
                instance.mark_email_verified()

            if self._verifycode_obj.msisdn is not None:
                instance.mark_msisdn_verified()

        return instance


class UpdateUserSerializer(BaseUserSerializer, ValidateUserSerializer):
    @transaction.atomic
    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            if hasattr(instance, key):
                # update password
                if key == 'password':
                    instance.set_password(value)
                else:
                    old_value = getattr(instance, key, None)
                    if old_value != value:
                        setattr(instance, key, value)
        instance.save()

        # mark verifycode as used
        if self._verifycode_obj:
            self._verifycode_obj.mark_used()
        return instance
