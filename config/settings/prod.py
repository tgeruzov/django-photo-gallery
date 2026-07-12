import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if (
    not SECRET_KEY
    or SECRET_KEY == "dev-key-change-in-production"  # noqa: S105 — это dev-дефолт, не секрет
    or len(SECRET_KEY) < 50
):
    raise ImproperlyConfigured("SECRET_KEY must be set to a strong unique value in production.")

DEBUG = env_bool("DEBUG", False)

if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_CACHE_URL", "redis://redis:6379/2"),
    }
}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_COOKIE_SECURE = True
# JS берёт CSRF-токен из скрытого поля формы — cookie ему не нужна (S10)
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Strict"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 2592000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# preload валиден только при max-age >= 1 года — включать явно через env (SE5)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
# Healthcheck-и ходят на http://127.0.0.1:8000/healthz изнутри контейнера:
# не редиректить их на https и пропускать локальный Host.
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
for _host in ("localhost", "127.0.0.1"):
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", True)
