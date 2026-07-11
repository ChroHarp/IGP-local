from django.http import HttpResponseForbidden

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .policies import approved_google_user_for_email


class ClosedSignupAdapter(DefaultAccountAdapter):
    """Disable local self-signup; administrators provision every user."""

    def is_open_for_signup(self, request):
        return False


class IGPAccountAdapter(DefaultSocialAccountAdapter):
    """Allow only pre-approved, active local users to sign in with Google."""

    def can_authenticate_by_email(self, login, email):
        return approved_google_user_for_email(email) is not None

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        verified_emails = [item.email for item in sociallogin.email_addresses if item.verified]
        if not any(approved_google_user_for_email(email) for email in verified_emails):
            raise ImmediateHttpResponse(HttpResponseForbidden("此帳號尚未獲授權使用系統。"))
