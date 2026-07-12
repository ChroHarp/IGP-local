import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "igp_project.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "igp_project.wsgi.application"
ASGI_APPLICATION = "igp_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_ADAPTER = "accounts.adapters.ClosedSignupAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapters.IGPAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = False
ACCOUNT_LOGIN_METHODS = {"username", "email"}
SOCIALACCOUNT_LOGIN_ON_GET = False
google_provider = {
    "SCOPE": ["profile", "email"],
    "AUTH_PARAMS": {"access_type": "online"},
    "OAUTH_PKCE_ENABLED": True,
    "EMAIL_AUTHENTICATION": True,
}
google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
if google_client_id and google_client_secret:
    google_provider["APPS"] = [
        {
            "client_id": google_client_id,
            "secret": google_client_secret,
            "key": "",
        }
    ]
SOCIALACCOUNT_PROVIDERS = {"google": google_provider}
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/accounts/login/"




