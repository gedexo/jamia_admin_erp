from core.base import BaseForm

from .models import UserProfile
from django import forms


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("first_name", "last_name", "email", "mobile", "whatsapp", "photo")
