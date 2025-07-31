import os
import hashlib
# from pixellib.tune_bg import alter_bg
from django.conf import settings
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException


from django.urls import reverse_lazy
from django.utils.http import urlencode

def build_url(viewname, kwargs=None, query_params=None):
    """
    Helper function to build a URL with optional path parameters and query parameters.

    :param viewname: Name of the view for reverse URL resolution.
    :param kwargs: Dictionary of path parameters.
    :param query_params: Dictionary of query parameters.
    :return: Constructed URL with query parameters.
    """
    url = reverse_lazy(viewname, kwargs=kwargs or {})
    if query_params:
        url = f"{url}?{urlencode(query_params)}"
    return url

# def get_image_hash(image_path):
#     with open(image_path, 'rb') as f:
#         return hashlib.md5(f.read()).hexdigest()

# def remove_bg_pixellib(input_path, subdir='processed_photos'):
#     """
#     Removes background using PixelLib and returns relative media path.
#     Skips processing if file already exists.
#     """
#     image_hash = get_image_hash(input_path)
#     output_dir = os.path.join(settings.MEDIA_ROOT, subdir)
#     os.makedirs(output_dir, exist_ok=True)

#     output_filename = f"{image_hash}.png"
#     output_path = os.path.join(output_dir, output_filename)

#     # Return cached image if it exists
#     if os.path.exists(output_path):
#         return os.path.join(subdir, output_filename)

#     # Load model and remove background
#     model_path = os.path.join(settings.BASE_DIR, "models", "deeplabv3_xception_tf_dim_ordering_tf_kernels.h5")
#     change_bg = alter_bg(model_type="pb")
#     change_bg.load_pascalvoc_model(model_path)
#     change_bg.color_bg(input_path, colors=(255, 255, 255), output_image_name=output_path)

#     return os.path.join(subdir, output_filename)


def send_notification_email(to_email, subject, html_content):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = getattr(settings, 'BREVO_API_KEY', None)
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        sender={"email": settings.DEFAULT_FROM_EMAIL, "name": "Jamia Admin ERP"},
        subject=subject,
        html_content=html_content
    )
    try:
        api_instance.send_transac_email(send_smtp_email)
        print(f"✅ Email sent successfully to {to_email}")
    except ApiException as e:
        print(f"❌ Exception when sending email: {e}")
        if "unauthorized" in str(e).lower() and "ip address" in str(e).lower():
            print("🔧 IP Authorization Issue:")
            print("   Your IP address is not authorized in Brevo.")
            print("   Please add your IP address to the authorized IPs list:")
            print("   https://app.brevo.com/security/authorised_ips")
            print("   Current IP: 103.42.196.84")
        elif "unauthorized" in str(e).lower():
            print("🔧 API Key Issue:")
            print("   Your Brevo API key might be invalid or expired.")
            print("   Please check your API key in the Brevo dashboard.")
        else:
            print("🔧 Other Email Error:")
            print("   Please check your Brevo account settings and API key.")
    except Exception as e:
        print(f"❌ Unexpected error when sending email: {e}")


def get_notification_email_html(message, url, domain=None):
    # If the url is relative and domain is provided, prepend domain
    if domain and url and url.startswith('/'):
        full_url = domain.rstrip('/') + url
    else:
        full_url = url
    logo_url = domain.rstrip('/') + '/static/app/assets/images/brand-logos/desktop-logo.png' if domain else 'https://jamiaerp.gedexo.com/static/app/assets/images/brand-logos/desktop-logo.png'
    return f"""
    <html>
    <head>
      <meta charset='UTF-8'>
      <meta name='viewport' content='width=device-width, initial-scale=1.0'>
      <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap\" rel=\"stylesheet\">
    </head>
    <body style=\"margin:0; padding:0; background:linear-gradient(135deg,#f6f8fa 0%,#e9f0fb 100%); font-family:'Inter',Arial,sans-serif;\">
      <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"min-height:100vh;\">
        <tr>
          <td align=\"center\" style=\"padding:40px 0;\">
            <table cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:480px; width:100%; background:#fff; border-radius:18px; box-shadow:0 4px 24px #e3eafc; overflow:hidden;\">
              <tr>
                <td style=\"padding:36px 36px 24px 36px; text-align:center;\">
                  <!-- Logo -->
                  <div style=\"margin-bottom:18px;\">
                    <img src='{logo_url}' alt='Jamia Admin ERP' style='width:120px; height:auto; border-radius:12px; box-shadow:0 2px 8px #e3eafc;'>
                  </div>
                  <h2 style=\"margin:0 0 10px 0; color:#2a7ae2; font-size:26px; font-weight:700; letter-spacing:0.5px;\">New Notification</h2>
                  <p style=\"margin:0 0 18px 0; color:#222; font-size:17px; line-height:1.6; font-weight:500;\">{message}</p>
                  <a href=\"{full_url}\" style=\"display:inline-block; margin:24px 0 0 0; padding:14px 38px; background:linear-gradient(90deg,#2a7ae2 0%,#5b9df9 100%); color:#fff; border-radius:6px; text-decoration:none; font-size:16px; font-weight:600; letter-spacing:0.2px; box-shadow:0 2px 8px #e3eafc; transition:background 0.2s;\">View Details</a>
                  <p style=\"margin:24px 0 0 0; color:#888; font-size:13px;\">This will take you to the request detail page.</p>
                  <p style=\"margin:18px 0 0 0; color:#bbb; font-size:12px;\">If the button above does not work, copy and paste this link into your browser:<br><span style=\"color:#2a7ae2; word-break:break-all;\">{full_url}</span></p>
                </td>
              </tr>
              <tr>
                <td style=\"background:#f6f8fa; text-align:center; padding:18px 36px; border-radius:0 0 18px 18px; color:#b0b8c9; font-size:12px;\">
                  This is an automated notification from <b>Jamia Admin ERP</b>.<br> &copy; {2025} Gedexo Technologies
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

def get_memo_notification_email_html(memo_title, memo_description, url, domain=None):
    """
    Generate HTML content for memo notification emails.
    """
    # If the url is relative and domain is provided, prepend domain
    if domain and url and url.startswith('/'):
        full_url = domain.rstrip('/') + url
    else:
        full_url = url
    logo_url = domain.rstrip('/') + '/static/app/assets/images/brand-logos/desktop-logo.png' if domain else 'https://jamiaerp.gedexo.com/static/app/assets/images/brand-logos/desktop-logo.png'
    
    # Truncate description for email preview
    description_preview = memo_description[:200] + "..." if len(memo_description) > 200 else memo_description
    
    return f"""
    <html>
    <head>
      <meta charset='UTF-8'>
      <meta name='viewport' content='width=device-width, initial-scale=1.0'>
      <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap\" rel=\"stylesheet\">
    </head>
    <body style=\"margin:0; padding:0; background:linear-gradient(135deg,#f6f8fa 0%,#e9f0fb 100%); font-family:'Inter',Arial,sans-serif;\">
      <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"min-height:100vh;\">
        <tr>
          <td align=\"center\" style=\"padding:40px 0;\">
            <table cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:520px; width:100%; background:#fff; border-radius:18px; box-shadow:0 4px 24px #e3eafc; overflow:hidden;\">
              <tr>
                <td style=\"padding:36px 36px 24px 36px; text-align:center;\">
                  <!-- Logo -->
                  <div style=\"margin-bottom:18px;\">
                    <img src='{logo_url}' alt='Jamia Admin ERP' style='width:120px; height:auto; border-radius:12px; box-shadow:0 2px 8px #e3eafc;'>
                  </div>
                  <h2 style=\"margin:0 0 10px 0; color:#2a7ae2; font-size:26px; font-weight:700; letter-spacing:0.5px;\">New Memo Published</h2>
                  <div style=\"background:#f8f9fa; border-radius:12px; padding:20px; margin:20px 0; text-align:left;\">
                    <h3 style=\"margin:0 0 12px 0; color:#333; font-size:18px; font-weight:600;\">{memo_title}</h3>
                    <p style=\"margin:0; color:#666; font-size:14px; line-height:1.5;\">{description_preview}</p>
                  </div>
                  <a href=\"{full_url}\" style=\"display:inline-block; margin:24px 0 0 0; padding:14px 38px; background:linear-gradient(90deg,#2a7ae2 0%,#5b9df9 100%); color:#fff; border-radius:6px; text-decoration:none; font-size:16px; font-weight:600; letter-spacing:0.2px; box-shadow:0 2px 8px #e3eafc; transition:background 0.2s;\">View Memo Details</a>
                  <p style=\"margin:24px 0 0 0; color:#888; font-size:13px;\">Click the button above to view the complete memo.</p>
                  <p style=\"margin:18px 0 0 0; color:#bbb; font-size:12px;\">If the button above does not work, copy and paste this link into your browser:<br><span style=\"color:#2a7ae2; word-break:break-all;\">{full_url}</span></p>
                </td>
              </tr>
              <tr>
                <td style=\"background:#f6f8fa; text-align:center; padding:18px 36px; border-radius:0 0 18px 18px; color:#b0b8c9; font-size:12px;\">
                  This is an automated notification from <b>Jamia Admin ERP</b>.<br> &copy; {2025} Gedexo Technologies
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """