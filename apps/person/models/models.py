from .user import *
from .verifycode import *

from django.contrib.auth.models import Group
from utils.generals import is_model_registered

__all__ = list()

# Add custom field to group
Group.add_to_class('is_default', models.BooleanField(default=False))


# https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#auth-custom-user
if not is_model_registered('person', 'User'):
    class User(User):
        class Meta(User.Meta):
            db_table = 'person_user'

    __all__.append('User')


# 1
if not is_model_registered('person', 'Profile'):
    class Profile(AbstractProfile):
        class Meta(AbstractProfile.Meta):
            db_table = 'person_profile'

    __all__.append('Profile')


# 2
if not is_model_registered('person', 'VerifyCode'):
    class VerifyCode(AbstractVerifyCode):
        class Meta(AbstractVerifyCode.Meta):
            db_table = 'person_verifycode'

    __all__.append('VerifyCode')
