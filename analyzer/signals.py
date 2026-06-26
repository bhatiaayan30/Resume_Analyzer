from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from .utils import send_welcome_email
import logging

logger = logging.getLogger(__name__)

@receiver(user_signed_up)
def handle_allauth_signup(request, user, **kwargs):
    """
    Signal handler for django-allauth signup (e.g. social login via Google/Apple/Microsoft).
    """
    try:
        domain = request.get_host() if request else None
        send_welcome_email(user, domain=domain)
    except Exception as e:
        logger.error(f"Failed to send welcome email to social signup user {user.email}: {e}")
