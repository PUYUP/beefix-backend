from django.db import transaction
from django.db.models import Q
from django.views.decorators.cache import never_cache
from django.core.exceptions import MultipleObjectsReturned, ValidationError, ObjectDoesNotExist
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _

from rest_framework import status as response_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError

from utils.validators import csrf_protect_drf
from utils.generals import get_model
from apps.person.utils.generator import (
    generate_token_uidb64_with_email,
    generate_token_uidb64_with_msisdn
)
from .serializers import CreateVerifyCodeSerializer, ValidateVerifyCodeSerializer

VerifyCode = get_model('person', 'VerifyCode')


@method_decorator(csrf_protect_drf, name='dispatch')
class VerifyCodeApiView(viewsets.ViewSet):
    """
    POST
    ---------------

    Param:

        {
            "email": "my@email.com",
            "msisdn": "09284255",
            "challenge": "VALIDATE_EMAIL"
        }

    Rules:

        username only used if user don't have active email
        eg; email auto-generate by system

        If email provided, msisdn not required
        If msisdn provide, email not required
    """
    lookup_field = 'passcode'
    lookup_value_regex = '[^/]+'
    permission_classes = (AllowAny,)

    def __init__(self, **kwargs):
        self._queryset = self._get_queryset()
        self._context = {}
        self._passcode = None
        super().__init__(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        self._passcode = kwargs.get('passcode')
        self._context.update({'request': request})
        return super().dispatch(request, *args, **kwargs)

    def _get_queryset(self):
        """General query affected for entire object"""
        query = VerifyCode.objects
        return query

    def _get_object(self):
        """Return single object"""
        try:
            object = self._queryset.get(passcode=self._passcode)
        except ObjectDoesNotExist:
            raise NotFound()
        return object

    @method_decorator(never_cache)
    @transaction.atomic
    def create(self, request, format=None):
        serializer = CreateVerifyCodeSerializer(
            data=request.data, context=self._context)
        if serializer.is_valid(raise_exception=True):
            try:
                serializer.save()
            except ValidationError as e:
                return Response({'detail': _(" ".join(e.messages))}, status=response_status.HTTP_406_NOT_ACCEPTABLE)

            return Response(serializer.data, status=response_status.HTTP_201_CREATED)
        return Response(serializer.errors, status=response_status.HTTP_400_BAD_REQUEST)

    @method_decorator(never_cache)
    @transaction.atomic
    def partial_update(self, request, passcode=None):
        return Response(_("Endpoint not used"), status=response_status.HTTP_400_BAD_REQUEST)

    # Sub-action validate verifycode
    @method_decorator(never_cache)
    @transaction.atomic
    @action(methods=['post'], detail=True, permission_classes=[AllowAny],
            url_path='validate', url_name='validate', lookup_field='passcode')
    def validate(self, request, passcode=None):
        """
        POST
        --------------

        Can't use both email and msisdn

        Format:

            {
                "email": "string",
                "msisdn": "string",
                "challenge": "string"
            }
        """
        email = request.data.get('email', None)
        msisdn = request.data.get('msisdn', None)
        challenge = request.data.get('challenge', None)

        # passing from param or url path
        _passcode = request.data.pop('passcode', passcode)

        try:
            obj = self._queryset.select_for_update() \
                .unverified_unused(**request.data, passcode=_passcode)
        except ObjectDoesNotExist:
            raise DRFValidationError(
                detail=_("Kode verifikasi salah atau kedaluwarsa"))

        # Generate token and uidb64 for password recovery
        if challenge == VerifyCode.ChallengeType.PASSWORD_RECOVERY:
            password_token = None
            password_uidb64 = None

            if 'email' in request.data:
                password_token, password_uidb64 = generate_token_uidb64_with_email(
                    email)

            if 'msisdn' in request.data:
                password_token, password_uidb64 = generate_token_uidb64_with_msisdn(
                    msisdn)

            if password_token and password_uidb64:
                self._context.update({
                    'password_token': password_token,
                    'password_uidb64': password_uidb64
                })
            else:
                # OPS! if token and uidb64 None
                # that indicate user with email or msisdn not registered
                # so stop here
                raise DRFValidationError(
                    detail=_("User tidak ditemukan"))

        serializer = ValidateVerifyCodeSerializer(
            obj, data=request.data, partial=True, context=self._context)
        if serializer.is_valid(raise_exception=True):
            try:
                serializer.save()
            except ValidationError as e:
                return Response({'detail': _(" ".join(e.messages))}, status=response_status.HTTP_406_NOT_ACCEPTABLE)

            return Response(serializer.data, status=response_status.HTTP_200_OK)
        return Response(serializer.errors, status=response_status.HTTP_400_BAD_REQUEST)

    # Sub-action check email or msisdn validated
    @method_decorator(never_cache)
    @transaction.atomic
    @action(methods=['post'], detail=False, permission_classes=[AllowAny],
            url_path='check', url_name='check')
    def check(self, request):
        """
        Params:

            {
                "email": "me@email.com",
                "msisdn": "02857272",
                "challenge": "whatever"
            }
        """
        email = request.data.get('email')
        msisdn = request.data.get('msisdn')
        challenge = request.data.get('challenge')

        if 'email' in request.data and 'msisdn' in request.data:
            raise DRFValidationError(
                detail=_("Can't use both email and msisdn"))

        obtain = email or msisdn

        try:
            self._queryset.get(Q(email=obtain) | Q(msisdn=obtain),
                               Q(is_verified=True), Q(is_used=True),
                               Q(challenge=challenge))
        except MultipleObjectsReturned as e:
            raise DRFValidationError(str(e))
        except ObjectDoesNotExist:
            raise DRFValidationError(
                detail=_("{} not validated".format(obtain)))
        return Response({'detail': _("{} has validated")}, status=response_status.HTTP_200_OK)
