from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest


class NoSignupAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # Only admins can create accounts, or use invite system


class NoSocialSignupAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin):
        return False  # Social login creates no new accounts; existing users only

    def get_signup_redirect_url(self, request):
        from django.contrib import messages

        messages.error(
            request,
            "Account creation is by invitation only. Contact the project team to request access.",
        )
        return "/accounts/login/"
