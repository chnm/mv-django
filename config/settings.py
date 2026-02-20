import os
from pathlib import Path

import environ
from dotenv import load_dotenv

load_dotenv(verbose=True, override=True)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
env = environ.Env()
READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=True)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

env = environ.FileAwareEnv(
    DEBUG=(bool, False),
)

# GENERAL
# ------------------------------------------------------------------------------

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-wu9#po37gfc6e$9bg#qt&fqk42+flc8zp^4xj)(=etm@_lg%#8",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost"])
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", default=["http://localhost"]
)

# Application definition

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "daphne",
    # dal must come before contrib.admin
    "dal",
    "dal_select2",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_tables2",
    "django_filters",
    "import_export",
    # allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.orcid",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.slack",
    # wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django_extensions",
    # tailwind
    "tailwind",
    "theme",
    # local apps
    "schema_viewer",
    "mapping_violence",
    "locations",
    "historical_dates",
    "content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # allauth
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

X_FRAME_OPTIONS = "SAMEORIGIN"

# DEBUG
# ------------------------------------------------------------------------------
# django-debug-toolbar
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": ["debug_toolbar.panels.redirects.RedirectsPanel"],
    "SHOW_TEMPLATE_CONTEXT": True,
}

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "content.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "NAME": env("DB_NAME", default="mapping_violence"),
        "USER": env("DB_USER", default="mapping_violence"),
        "PASSWORD": env("DB_PASS", default="password"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # allauth specific authentication methods, such as login by email
    "allauth.account.auth_backends.AuthenticationBackend",
]


# allauth
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
ACCOUNT_EMAIL_VERIFICATION = (
    "optional"  # Changed from 'mandatory' to fix ConnectionRefusedError
)
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email", "username*", "password1*", "password2*"]
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_SESSION_REMEMBER = True
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
# Custom adapter to prevent any signups unless invited
ACCOUNT_ADAPTER = "config.adapters.NoSignupAdapter"
SOCIALACCOUNT_ADAPTER = "config.adapters.NoSocialSignupAdapter"
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True  # match social email to existing account
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = (
    True  # auto-connect without manual confirmation
)

# allauth: provider specific settings
SOCIALACCOUNT_PROVIDERS = {
    "orcid": {
        "BASE_DOMAIN": "orcid.org",
        "MEMBER_API": False,
        "APP": {
            "client_id": env("ALLAUTH_ORCID_CLIENT_ID", default="PLACEHOLDER"),
            "secret": env("ALLAUTH_ORCID_CLIENT_SECRET", default="PLACEHOLDER"),
        },
    },
    "github": {
        "VERIFIED_EMAIL": True,
        "APP": {
            "client_id": env("ALLAUTH_GITHUB_CLIENT_ID", default="PLACEHOLDER"),
            "secret": env("ALLAUTH_GITHUB_CLIENT_SECRET", default="PLACEHOLDER"),
        },
    },
    "slack": {
        "VERIFIED_EMAIL": True,
        "SCOPE": ["openid", "profile", "email"],
        "AUTH_PARAMS": {
            "auth_type": "reauthenticate",
        },
        "APP": {
            "client_id": env("ALLAUTH_SLACK_CLIENT_ID", default="PLACEHOLDER"),
            "secret": env("ALLAUTH_SLACK_CLIENT_SECRET", default="PLACEHOLDER"),
            "key": "",
        },
    },
}

# Email settings for development and production
if DEBUG:
    # In development, print emails to console instead of sending them
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # In production, configure proper SMTP settings
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST", default="localhost")
    EMAIL_PORT = env("EMAIL_PORT", default=587)
    EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True
# Theme
TAILWIND_APP_NAME = "theme"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_URL = "static/"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "static"),)
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Storage backend
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Media files
OBJ_STORAGE = env("OBJ_STORAGE", default=False)
if OBJ_STORAGE:
    AWS_ACCESS_KEY_ID = env("OBJ_STORAGE_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("OBJ_STORAGE_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("OBJ_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = env("OBJ_STORAGE_ENDPOINT_URL")

    MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/"

    # override default storage backend for media
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
    }
else:
    MEDIA_URL = "media/"
    MEDIA_ROOT = os.path.join(BASE_DIR, "mediafiles")

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Wagtail settings
WAGTAIL_SITE_NAME = "Mapping Violence"
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL", default="http://localhost:8000")

# Django Unfold Admin Configuration
UNFOLD = {
    "SITE_TITLE": "Mapping Violence Admin",
    "SITE_HEADER": "Mapping Violence",
    "SITE_URL": "/",
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "196 144 254",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
        },
    },
    "EXTENSIONS": {
        "modeltranslation": {
            "flags": {
                "en": "🇬🇧",
                "fr": "🇫🇷",
                "nl": "🇳🇱",
            },
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Data Management",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Violence Events",
                        "icon": "gavel",
                        "link": "/admin/mapping_violence/crime/",
                    },
                    {
                        "title": "People",
                        "icon": "people",
                        "link": "/admin/mapping_violence/person/",
                    },
                    {
                        "title": "Relationship Types",
                        "icon": "people",
                        "link": "/admin/mapping_violence/personrelationtype/",
                    },
                ],
            },
            {
                "title": "Reference Data",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Cities",
                        "icon": "location_city",
                        "link": "/admin/locations/city/",
                    },
                    {
                        "title": "Locations",
                        "icon": "place",
                        "link": "/admin/locations/location/",
                    },
                    {
                        "title": "Events",
                        "icon": "event",
                        "link": "/admin/mapping_violence/event/",
                    },
                    {
                        "title": "Weapons",
                        "icon": "dangerous",
                        "link": "/admin/mapping_violence/weapon/",
                    },
                    {
                        "title": "Historical Dates",
                        "icon": "date_range",
                        "link": "/admin/historical_dates/historicaldate/",
                    },
                ],
            },
            {
                "title": "Website Content",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Content Management",
                        "icon": "edit",
                        "link": "/cms/",
                    },
                ],
            },
            {
                "title": "System Configuration",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": "/admin/auth/user/",
                    },
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": "/admin/auth/group/",
                    },
                ],
            },
            {
                "title": "Social Authentication",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Social Applications",
                        "icon": "apps",
                        "link": "/admin/socialaccount/socialapp/",
                    },
                    {
                        "title": "Social Accounts",
                        "icon": "account_circle",
                        "link": "/admin/socialaccount/socialaccount/",
                    },
                ],
            },
        ],
    },
}
