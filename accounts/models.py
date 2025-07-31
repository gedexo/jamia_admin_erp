from core.choices import USERTYPE_CHOICES
from core.functions import generate_fields

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import BaseUserManager
from django.db import models
from django.urls import reverse_lazy


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular user with an email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and return a superuser with an email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    usertype = models.CharField("Permissions", max_length=30, choices=USERTYPE_CHOICES)

    USERNAME_FIELD = 'email'  # Set email as the username field
    REQUIRED_FIELDS = []  # Remove username from required fields

    objects = CustomUserManager()  # Assign the custom user manager

    def get_fields(self):
        return generate_fields(self)

    def get_absolute_url(self):
        return reverse_lazy("accounts:user_detail", kwargs={"pk": self.pk})

    @staticmethod
    def get_list_url():
        return reverse_lazy("accounts:user_list")

    @staticmethod
    def get_create_url():
        return reverse_lazy("accounts:user_create")

    def get_update_url(self):
        return reverse_lazy("accounts:user_update", kwargs={"pk": self.pk})

    def get_delete_url(self):
        return reverse_lazy("accounts:user_delete", kwargs={"pk": self.pk})

    @property
    def fullname(self):
        return self.username

    def __str__(self):
        return self.email

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        # Only enforce uniqueness for usertypes other than 'College'
        if self.usertype != 'College':
            qs = User.objects.filter(usertype=self.usertype)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'usertype': f"A user with usertype '{self.usertype}' already exists. Only 'College' usertype can have multiple users."})
