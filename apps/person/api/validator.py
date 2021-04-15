from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.conf import settings

from rest_framework import serializers
from utils.generals import get_model

User = get_user_model()
VerifyCode = get_model('person', 'VerifyCode')


# Password verification
class PasswordValidator(object):
    requires_context = True

    def __call__(self, value, serializer_field):
        validate_password(value)


# Check duplicate email if has verified
class EmailDuplicateValidator(object):
    requires_context = True

    def __call__(self, value, serializer_field):
        user = User.objects.filter(
            email=value,
            is_email_verified=settings.STRICT_EMAIL_VERIFIED
        )

        if user.exists():
            raise serializers.ValidationError(
                _("Email {email} sudah terdaftar.".format(email=value))
            )


# Check duplicate msisdn if has verified
class MsisdnDuplicateValidator(object):
    requires_context = True

    def __call__(self, value, serializer_field):
        user = User.objects.filter(
            msisdn=value,
            is_msisdn_verified=settings.STRICT_MSISDN_VERIFIED
        )

        if user.exists():
            raise serializers.ValidationError(
                _("Nomor telepon sudah digunakan"))


# Check duplicate msisdn if has verified
class MsisdnNumberValidator(object):
    requires_context = True

    def __call__(self, value, serializer_field):
        if not value.isnumeric() or not value:
            raise serializers.ValidationError(
                _("Nomor telepon hanya boleh angka"))
