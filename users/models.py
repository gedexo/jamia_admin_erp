import os
import uuid
from django.db import models
from django.urls import reverse_lazy
from easy_thumbnails.fields import ThumbnailerImageField

from core.base import BaseModel


class UserProfile(BaseModel):
    user = models.OneToOneField("accounts.User", on_delete=models.PROTECT, limit_choices_to={"is_active": True}, related_name="employee", null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    profile_id = models.CharField(max_length=128, unique=True, null=True)
    email = models.EmailField(max_length=128, null=True)
    mobile = models.CharField(max_length=128, blank=True, null=True)
    whatsapp = models.CharField(max_length=128, blank=True, null=True)
    photo = ThumbnailerImageField(blank=True, null=True, upload_to="users/photos/")

    def __str__(self):
        return str(self.user)

    def fullname(self):
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def get_absolute_url(self):
        return reverse_lazy("users:user_profile_detail", kwargs={"pk": self.pk})

    def get_image_url(self):
        if self.photo:
            return self.photo.url
        return f"https://ui-avatars.com/api/?name={self.user[:2]}&background=fdc010&color=fff&size=128"

    @staticmethod
    def get_list_url():
        return reverse_lazy("users:user_profile_list")

    @staticmethod
    def get_create_url():
        return reverse_lazy("users:user_profile_create")

    def get_delete_url(self):
        return reverse_lazy("users:user_profile_delete", kwargs={"pk": self.pk})

    def get_update_url(self):
        return reverse_lazy("users:user_profile_update", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.profile_id:
            from .functions import generate_profile_id
            self.profile_id = generate_profile_id()
        if not self.pk and self.photo:
            self.photo.name = f"{uuid.uuid4()}{os.path.splitext(self.photo.name)[1]}"
        super().save(*args, **kwargs)