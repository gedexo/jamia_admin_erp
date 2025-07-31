import calendar
import re

from django import template
from django.conf import settings


register = template.Library()


@register.filter(name="times")
def times(number):
    return range(number)


@register.filter()
def class_name(value):
    return value.__class__.__name__


@register.filter()
def make_title(value):
    return re.sub(r"(\w)([A-Z])", r"\1 \2", value)


def pop_and_get_app(apps, key, app_label):
    for index, app in enumerate(apps):
        if app[key] == app_label:
            return apps.pop(index)
    return None


@register.filter
def sort_apps(apps):
    new_apps = []
    order = settings.APP_ORDER
    for app_label in order.keys():
        obj = pop_and_get_app(apps, "app_label", app_label)
        if obj:
            new_apps.append(obj)
    apps = new_apps + apps
    for app in apps:
        models = app.get("models")
        app_label = app.get("app_label")
        new_models = []
        order_models = settings.APP_ORDER.get(app_label, [])
        for model in order_models:
            obj = pop_and_get_app(models, "object_name", model)
            if obj:
                new_models.append(obj)
        models = new_models + models
        app["models"] = models
    return apps


@register.filter
def month_name(month_number):
    return calendar.month_name[month_number]


@register.filter
def user_type_allowed(user_type, allowed_types):
    return user_type in allowed_types


@register.filter
def filter_by_status(objects, status):
    return objects.filter(status=status)


@register.filter
def get_detail_url_name(record):
    """Get the detail URL name for a model record"""
    
    app_label = record._meta.app_label
    model_name = record._meta.model_name
    
    snake_case_name = re.sub(r'(?<!^)(?=[A-Z])', '_', model_name).lower()
    
    url_name = f"{app_label}:{snake_case_name}_detail"
    
    # Debug logging
    print(f"DEBUG: Model: {model_name}, App: {app_label}, URL: {url_name}")
    
    return url_name


@register.filter
def get_absolute_url_string(record):
    """Convert reverse_lazy to string for use in templates"""
    try:
        return str(record.get_absolute_url())
    except Exception as e:
        print(f"Error getting absolute URL for {record}: {e}")
        return "#"
