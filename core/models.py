from core.choices import MODULE_CHOICES
from core.choices import MONTH_CHOICES
from core.choices import VIEW_TYPE_CHOICES
from core.choices import YEAR_CHOICES

from .base import BaseModel
from django.db import models
from django.urls import reverse_lazy
from django.conf import settings


def get_default_document_settings():
    return {
        "invoice": {
            "airline": {"prefix": "AI", "start_count": 1},
            "hotel": {"prefix": "HT", "start_count": 1},
            "visa": {"prefix": "VI", "start_count": 1},
            "miscellaneous": {"prefix": "MS", "start_count": 1},
            "transportation": {"prefix": "TR", "start_count": 1},
            "package": {"prefix": "PI", "start_count": 1},
        },
        "purchase": {
            "airline": {"prefix": "PA", "start_count": 1},
            "hotel": {"prefix": "PH", "start_count": 1},
            "visa": {"prefix": "PV", "start_count": 1},
            "miscellaneous": {"prefix": "PM", "start_count": 1},
            "transportation": {"prefix": "PT", "start_count": 1},
            "package": {"prefix": "PP", "start_count": 1},
        },
        "estimate": {
            "airline": {"prefix": "QTAI", "start_count": 1},
            "hotel": {"prefix": "QTHT", "start_count": 1},
            "visa": {"prefix": "QTVI", "start_count": 1},
            "miscellaneous": {"prefix": "QTMS", "start_count": 1},
            "transportation": {"prefix": "QTTR", "start_count": 1},
            "package": {"prefix": "QTPI", "start_count": 1},
        },
        "receipt": {"prefix": "RCPT", "start_count": 1},
        "payment": {"prefix": "PY", "start_count": 1},
        "jv": {"prefix": "JV", "start_count": 1},
    }


class Setting(BaseModel):
    instance_id = models.CharField(max_length=50, null=True)
    access_token = models.CharField(max_length=50, null=True)

    def __str__(self):
        return str(self.access_token)

    class Meta:
        verbose_name = "Settings"
        verbose_name_plural = "Settings"


class Link(models.Model):
    """
    A model representing a link, which can be displayed in the application.
    """

    value = models.CharField("Title", max_length=200, blank=True, null=True)
    description = models.CharField(max_length=200)
    module = models.CharField(max_length=200, choices=MODULE_CHOICES)
    view = models.CharField(max_length=200)
    name = models.CharField(max_length=200, unique=True)
    view_type = models.CharField(max_length=200, choices=VIEW_TYPE_CHOICES)
    is_dashboard_link = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    is_quick_access = models.BooleanField(default=False)
    created = models.DateTimeField(db_index=True, auto_now_add=True)

    employee_access = models.BooleanField(default=True)
    admin_staff_access = models.BooleanField(default=False)

    class Meta:
        ordering = ("view",)

    def gen_link(self):
        name = self.name.split(".")
        if self.view_type in ["CreateView", "DashboardView", "ListView", "TemplateView", "View"]:
            try:
                return reverse_lazy(f"{name[0]}:{name[1]}") if len(name) == 2 else reverse_lazy(f"{name[0]}")
            except:
                return ""
        return ""

    def __str__(self):
        return str(self.view)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    url = models.URLField()
    is_read = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user}: {self.message}"