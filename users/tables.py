from core.base import BaseTable

from .models import UserProfile
from django_tables2 import columns


class UserProfileTable(BaseTable):
    profile_id = columns.Column(linkify=True)
    created = None
    fullname = columns.Column(verbose_name="Name", order_by="first_name")
    user__usertype = columns.Column(verbose_name="User Type")

    class Meta(BaseTable.Meta):
        model = UserProfile
        fields = ("profile_id", "fullname", "mobile", "email", "user__usertype",)