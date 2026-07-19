import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me-in-production")

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "pgvector",
    "users",
    "menu",
    "orders",
    "reservations",
    "payments",
    "cart",
    "agent",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.RequestIDMiddleware",
]

ROOT_URLCONF = "config.urls"

# ── Production: track LLM provider usage per minute ─────────────────────
LLM_TRACK_USAGE = os.getenv("LLM_TRACK_USAGE", "true").lower() == "true"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "restaurant_agent"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

if os.getenv("USE_SQLITE", "false").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "120/minute",
        "chat_stream": "15/minute",
        "payment_webhook": "30/minute",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

RESTAURANT_PAYMENT_PHONE = os.getenv("RESTAURANT_PAYMENT_PHONE", "+254 700 123 456")

TAX_RATE: float = 0.0825
DELIVERY_FEE: float = 4.99

LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("HF_TOKEN", ""))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("HF_BASE_URL", "https://api-inference.huggingface.co/v1"))
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct"))
LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY", "")
LLM_FALLBACK_BASE_URL = os.getenv("LLM_FALLBACK_BASE_URL", "")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
HF_EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY", "")
CHAPA_PUBLIC_KEY = os.getenv("CHAPA_PUBLIC_KEY", "")
CHAPA_WEBHOOK_SECRET = os.getenv("CHAPA_WEBHOOK_SECRET", "")
PAYMENT_DEMO_MODE = os.getenv("PAYMENT_DEMO_MODE", "true").lower() == "true"

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@restaurant-agent.com")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {request_id} {message}",
            "style": "{",
        },
    },
    "filters": {
        "request_id": {
            "()": "config.middleware.RequestIDFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "agent": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "payments": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "reservations": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "menu": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
