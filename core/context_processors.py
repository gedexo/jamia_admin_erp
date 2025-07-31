from django.conf import settings


def main_context(request):
    user = request.user if request.user.is_authenticated else None
    name = user.email if user else None

    return {
        "current_employee": user,
        "default_user_avatar": f"https://ui-avatars.com/api/?name={name or ''}&background=fdc010&color=fff&size=128",
        "app_settings": settings.APP_SETTINGS,
    }
