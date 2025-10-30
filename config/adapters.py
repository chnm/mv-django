from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # Only admins can create accounts, or use invite system
