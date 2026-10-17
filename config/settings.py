import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_int(name, default, minimum=0):
    """Целое из окружения; опечатка в значении - понятная ошибка при старте, а не traceback."""
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        number = int(value)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an integer, got {value!r}.") from None
    if number < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}, got {number}.")
    return number


DEBUG = env_bool("DEBUG", False)
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-key"  # noqa: S105

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "gallery",
    "django_cleanup.apps.CleanupConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "gallery"),
        "USER": os.environ.get("DB_USER", "gallery"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "gallery"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        # Соединение, которое база оборвала (перезапуск PostgreSQL), проверяется
        # перед запросом, а не роняет его ошибкой
        "CONN_HEALTH_CHECKS": True,
        # Недоступная база - быстрая ошибка и 503 на /healthz, а не зависший воркер
        "OPTIONS": {"connect_timeout": 10},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "").strip() or BASE_DIR / "media")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 100, minimum=1)
# 1 = оригиналы удаляются безвозвратно после генерации оптимизированной версии
DELETE_ORIGINAL_AFTER_OPTIMIZE = env_bool("DELETE_ORIGINAL_AFTER_OPTIMIZE", False)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 2592000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"

# HSTS preload - отдельное решение владельца домена: из списка предзагрузки
# браузеров быстро не выйти, поэтому check --deploy об этом не напоминает
SILENCED_SYSTEM_CHECKS = ["security.W021"]

LOG_LEVEL = os.environ.get("LOG_LEVEL", "").strip().upper() or "INFO"
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise ImproperlyConfigured(
        f"LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL, got {LOG_LEVEL!r}."
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    # Время, уровень и источник в каждой строке: по логам контейнера видно, что и когда случилось
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}
