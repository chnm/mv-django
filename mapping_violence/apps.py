from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mapping_violence"

    def ready(self):
        # Fix hardcoded double-slash bug in allauth's Slack provider
        # https://slack.com//openid/connect/authorize → https://slack.com/openid/connect/authorize
        from allauth.socialaccount.providers.slack.views import SlackOAuth2Adapter
        SlackOAuth2Adapter.authorize_url = "https://slack.com/openid/connect/authorize"

