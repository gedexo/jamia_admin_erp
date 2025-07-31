from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from django.db.models.signals import post_save
from core.models import Notification
from core.utils import send_notification_email, get_notification_email_html, get_memo_notification_email_html
from django.contrib.sites.models import Site

@receiver(user_logged_in)
def post_login(sender, user, request, **kwargs):
    """
    Set the initial time for assignment checks when a user logs in.
    """
    request.session['last_assignment_check_time'] = timezone.now().isoformat()

@receiver(post_save, sender=Notification)
def send_notification_email_signal(sender, instance, created, **kwargs):
    # Try to get the domain from the request if available (for signals triggered by a view)
    request = None
    if hasattr(instance, '_request'):
        request = instance._request
    domain = None
    if request:
        domain = request.scheme + '://' + request.get_host()
    else:
        # Fallback to Site framework or settings
        try:
            domain = 'https://' + Site.objects.get_current().domain
        except Exception:
            from django.conf import settings
            domain = getattr(settings, 'DEFAULT_DOMAIN', 'http://localhost:8000')
    if created and instance.user.email:
        # Check if this is a memo notification
        if "memo published" in instance.message.lower():
            subject = "New Memo Published - Jamia Admin ERP"
            # Extract memo title from the message
            memo_title = instance.message.replace("New memo published: ", "")
            # Get memo description if available
            memo_description = getattr(instance, '_memo_description', "A new memo has been published and is now available for viewing.")
            # For memo notifications, we'll use a more specific template
            html_content = get_memo_notification_email_html(
                memo_title=memo_title,
                memo_description=memo_description,
                url=instance.url,
                domain=domain
            )
        else:
            subject = "New Notification from Jamia Admin ERP"
            html_content = get_notification_email_html(instance.message, instance.url, domain=domain)
        
        send_notification_email(instance.user.email, subject, html_content)