import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "dev-key-change-in-production" or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("SECRET_KEY must be set to a strong unique value in production.")

DEBUG = env_bool("DEBUG", False)

if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 2592000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", True)
