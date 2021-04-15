import uuid

from django.conf import settings

from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError

from utils.validators import non_python_keyword, identifier_validator


class UserManagerExtend(UserManager):
    @transaction.atomic()
    def create_user(self, username, email, password, **extra_fields):
        msisdn = extra_fields.get('msisdn')
        if not msisdn and settings.STRICT_MSISDN:
            raise ValueError(_("The given msisdn must be set"))

        if not email and settings.STRICT_EMAIL:
            raise ValueError(_("The given email must be set"))

        return super().create_user(username, email=email, password=password, **extra_fields)


# Extend User
# https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#substituting-a-custom-user-model
class User(AbstractUser):
    _msisdn_required = not settings.STRICT_MSISDN
    _email_required = not settings.STRICT_EMAIL

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    msisdn = models.CharField(blank=_msisdn_required, null=_msisdn_required,
                              unique=settings.STRICT_EMAIL_DUPLICATE, max_length=14)
    email = models.EmailField(_('email address'), blank=_email_required,
                              null=_email_required, unique=settings.STRICT_MSISDN_DUPLICATE)
    is_email_verified = models.BooleanField(default=False, null=True)
    is_msisdn_verified = models.BooleanField(default=False, null=True)

    objects = UserManagerExtend()

    class Meta(AbstractUser.Meta):
        app_label = 'person'

    def clean(self, *args, **kwargs):
        raise ValidationError({
            'title': _('Missing title.'),
            'pub_date': _('Invalid date.'),
        })

    @property
    def name(self):
        full_name = '{}{}'.format(self.first_name, ' ' + self.last_name)
        return full_name if self.first_name else self.username

    def mark_email_verified(self):
        self.is_email_verified = True
        self.save(update_fields=['is_email_verified'])

    def mark_msisdn_verified(self):
        self.is_msisdn_verified = True
        self.save(update_fields=['is_msisdn_verified'])

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


class AbstractProfile(models.Model):
    class GenderChoice(models.TextChoices):
        UNDEFINED = 'unknown', _("Unknown")
        MALE = 'male', _("Male")
        FEMALE = 'female', _("Female")

    _UPLOAD_TO = 'images/user'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    create_at = models.DateTimeField(auto_now_add=True, db_index=True)
    update_at = models.DateTimeField(auto_now=True)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='profile')

    headline = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(choices=GenderChoice.choices, blank=True, null=True,
                              default=GenderChoice.UNDEFINED, max_length=255,
                              validators=[identifier_validator, non_python_keyword])
    birthdate = models.DateField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    picture = models.ImageField(upload_to=_UPLOAD_TO, max_length=500,
                                null=True, blank=True)
    picture_original = models.ImageField(upload_to=_UPLOAD_TO, max_length=500,
                                         null=True, blank=True)

    class Meta:
        abstract = True
        app_label = 'person'
        ordering = ['-user__date_joined']
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")

    def __str__(self):
        return self.user.username

    @ property
    def first_name(self):
        return self.user.first_name

    @ property
    def last_name(self):
        return self.user.last_name
