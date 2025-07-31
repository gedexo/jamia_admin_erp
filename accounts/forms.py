from core.base import BaseForm

from .models import User
from django import forms
from django.contrib.auth.forms import AuthenticationForm

class UserForm(BaseForm):
    class Meta:
        model = User
        fields = ("email", "usertype", "password")

    def clean(self):
        cleaned_data = super().clean()
        # Model-level clean() will be called automatically
        return cleaned_data