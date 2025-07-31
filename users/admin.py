from core.base import BaseAdmin

from .models import UserProfile
from django.contrib import admin

admin.site.register(UserProfile)
class UserProfileAdmin(BaseAdmin):
    list_display = ("profile_id", "fullname", "mobile", "user_type")
    search_fields = ("profile_id", "fullname", "mobile", "user_type")
    list_filter = ("user_type",)