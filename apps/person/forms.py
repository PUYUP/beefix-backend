from django import forms
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

User = get_user_model()


class UserChangeFormExtend(UserChangeForm):
    """ Override user Edit form """

    def clean_email(self):
        email = self.cleaned_data.get('email', None)
        username = self.cleaned_data.get('username', None)

        # Make user email filled
        if email:
            # Validate each user has different email
            if User.objects.filter(email=email).exclude(username=username).exists():
                raise forms.ValidationError(
                    _("Email {email} already registered.".format(email=email)))
        return email


class UserCreationFormExtend(UserCreationForm):
    """ Override user Add form """

    def clean_email(self):
        email = self.cleaned_data.get('email', None)
        username = self.cleaned_data.get('username', None)

        # Make user email filled
        if email:
            # Validate each user has different email
            if User.objects.filter(email=email).exclude(username=username).exists():
                raise forms.ValidationError(
                    _("Email {email} already registered.".format(email=email)),
                    passcode='email_used',
                )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()

        groups = self.changed_data.get('groups')
        if groups:
            setattr(user, 'groups_input', groups)
        return user
