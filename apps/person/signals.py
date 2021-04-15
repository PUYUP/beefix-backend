from django.db import transaction, IntegrityError
from django.db.models import Q, Case, When, Value
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist

from utils.generals import get_model

# Celery task
from apps.person.tasks import send_verifycode_email

Profile = get_model('person', 'Profile')


@transaction.atomic
def user_save_handler(sender, instance, created, **kwargs):
    if created:
        profile = getattr(instance, 'profile', None)
        if profile is None:
            try:
                Profile.objects.create(user=instance)
            except IntegrityError:
                pass

        # Get groups if user created by admin
        groups_input = getattr(instance, 'groups_input', None)
        if groups_input is None:
            # This action indicate user self registration
            # Set default user groups
            try:
                group = Group.objects.get(is_default=True)
                instance.groups.add(group)
            except ObjectDoesNotExist:
                pass

    if not created:
        # create Profile if not exist
        if not hasattr(instance, 'profile'):
            Profile.objects.create(user=instance)


@transaction.atomic
def group_save_handler(sender, instance, created, **kwargs):
    is_default = getattr(instance, 'is_default')
    if is_default:
        groups = Group.objects.exclude(id=instance.id)
        if groups.exists():
            groups.update(is_default=False)


@transaction.atomic
def verifycode_save_handler(sender, instance, created, **kwargs):
    # create tasks
    # run only on resend and created
    if instance.is_used == False and instance.is_verified == False:
        if instance.email:
            data = {
                'email': getattr(instance, 'email', None),
                'passcode': getattr(instance, 'passcode', None)
            }
            # send_verifycode_email.delay(data) # with celery
            # send_verifycode_email(data)  # without celery

        # mark oldest VerifyCode as expired
        obtain = instance.msisdn or instance.email
        cls = instance.__class__
        oldest = cls.objects \
            .filter(
                Q(challenge=instance.challenge),
                Q(email=obtain) | Q(msisdn=obtain),
                Q(is_used=False), Q(is_expired=False)
            ).exclude(passcode=instance.passcode)

        if oldest.exists():
            oldest.update(is_expired=True)
