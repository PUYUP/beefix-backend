from django.apps import AppConfig
from django.db.models.signals import post_save


class PersonConfig(AppConfig):
    name = 'apps.person'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from django.conf import settings
        from django.contrib.auth.models import Group
        from utils.generals import get_model
        from .signals import user_save_handler, group_save_handler, verifycode_save_handler

        VerifyCode = get_model('person', 'VerifyCode')

        # User
        post_save.connect(user_save_handler, sender=settings.AUTH_USER_MODEL,
                          dispatch_uid='user_save_signal')

        # Verifycode
        post_save.connect(verifycode_save_handler, sender=VerifyCode,
                          dispatch_uid='verifycode_save_signal')

        # Group
        post_save.connect(group_save_handler, sender=Group,
                          dispatch_uid='group_save_signal')
