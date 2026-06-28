"""
settings.py — Django project settings for resume_analyzer.

Uses python-decouple to read sensitive values from .env.
Copy .env.example → .env and fill in your values before running.
"""

from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Security ───────────────────────────────────────────────────
from django.core.exceptions import ImproperlyConfigured
DEBUG = config("DEBUG", default=False, cast=bool)

# Require keys in production
if not DEBUG:
    SECRET_KEY = config("SECRET_KEY")
    ENCRYPTION_KEY = config("ENCRYPTION_KEY")
else:
    SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-this-before-deploying")
    ENCRYPTION_KEY = config("ENCRYPTION_KEY", default="m4XLU7wYoDxNunv7YahZPCmja_ryje0JiOYL5LBK1s0=")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())
ALLOWED_HOSTS.append(".vercel.app")
ALLOWED_HOSTS.append(".onrender.com")

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")
if "https://*.onrender.com" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://*.onrender.com")



# ── Applications ───────────────────────────────────────────────
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
    "allauth.socialaccount.providers.apple",
    "allauth.socialaccount.providers.microsoft",
    "analyzer.apps.AnalyzerConfig",
]

SITE_ID = 1



MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Add Whitenoise for static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "resume_analyzer.urls"


# ── Templates ──────────────────────────────────────────────────
# DIRS points Django at your top-level templates/ folder.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # ← required for base.html etc.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "resume_analyzer.wsgi.application"


# ── Database ───────────────────────────────────────────────────
# SQLite is fine for local dev. Swap to PostgreSQL for production.
DATABASE_URL = config("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=0 if DEBUG else 600)}


# ── Auth ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ── Email Configuration ─────────────────────────────────────────────────
# By default Django prints emails to the console (DEBUG mode). To send real emails via
# Gmail, set USE_SMTP=True in your .env and provide EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.
USE_SMTP = config("USE_SMTP", default=False, cast=bool)

PASSWORD_RESET_TIMEOUT = 900  # 15 minutes validity

if USE_SMTP:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
    EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
    EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
    EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="your_email@gmail.com")
    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="your_app_password")
    DEFAULT_FROM_EMAIL = f"Resume Analyzer <{EMAIL_HOST_USER}>"
else:
    # Console backend – useful for local development and debugging
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "Resume Analyzer <noreply@resumeanalyzer.com>"


# ── Internationalisation ───────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ── Static files ───────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── File upload limits ─────────────────────────────────────────
# 5 MB total request / 5 MB per file.
# Views also enforce a 2 MB per-file cap in code.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


# ── AI ─────────────────────────────────────────────────────────
# Read in utils.py via getattr(settings, 'GROQ_API_KEY').
GROQ_API_KEY = config("GROQ_API_KEY", default="")


# ── Razorpay Settings ────────────────────────────────────────────
RAZORPAY_KEY_ID = config("RAZORPAY_KEY_ID", default="rzp_test_placeholder")
RAZORPAY_KEY_SECRET = config("RAZORPAY_KEY_SECRET", default="secret_placeholder")
RAZORPAY_WEBHOOK_SECRET = config("RAZORPAY_WEBHOOK_SECRET", default="whsec_placeholder")

# ── API Keys ───────────────────────────────────────────────────
APP_API_KEY = config("APP_API_KEY", default="dummy-api-key-change-me")

# Plan IDs for Razorpay
RAZORPAY_PLAN_ID_49 = config("RAZORPAY_PLAN_ID_49", default="")
RAZORPAY_PLAN_ID_149 = config("RAZORPAY_PLAN_ID_149", default="")
RAZORPAY_PLAN_ID_299 = config("RAZORPAY_PLAN_ID_299", default="")
RAZORPAY_PLAN_ID_999 = config("RAZORPAY_PLAN_ID_999", default="")

# ── Twilio Settings (SMS) ──────────────────────────────────────
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_PHONE_NUMBER = config("TWILIO_PHONE_NUMBER", default="")

# ── Allauth Providers ──────────────────────────────────────────
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGIN_METHODS = {'email', 'username'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": config("GOOGLE_CLIENT_ID", default="dummy"),
            "secret": config("GOOGLE_SECRET", default="dummy"),
            "key": ""
        }
    },
    "apple": {
        "APP": {
            "client_id": config("APPLE_CLIENT_ID", default="dummy"),
            "secret": config("APPLE_KEY_ID", default="dummy"),
            "key": config("APPLE_TEAM_ID", default="dummy"),
            "settings": {
                "certificate_key": config("APPLE_PRIVATE_KEY", default=""),
            }
        }
    },
    "microsoft": {
        "APP": {
            "client_id": config("MICROSOFT_CLIENT_ID", default="dummy"),
            "secret": config("MICROSOFT_SECRET", default="dummy"),
            "settings": {
                "tenant": config("MICROSOFT_TENANT", default="common"),
            }
        }
    }
}
