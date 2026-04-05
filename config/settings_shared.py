import os
from pathlib import Path

from .settings.base import *  # noqa: F401,F403

DEBUG = env_bool("DEBUG", False)
SECURE_BY_DEFAULT = not DEBUG

SHARED_HOSTING = True
APPEND_SLASH = True
FORCE_SCRIPT_NAME = ""

# Shared hosting should keep uploads and image generation in the current process.
ENABLE_BACKGROUND_TASKS = False

# Shared Apache/mod_wsgi deployments serve static and media files directly.
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles")).expanduser()
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media")).expanduser()

# Lower defaults reduce the chance of exhausting worker memory on shared plans.
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 25)
MAX_JSON_PAGE_SIZE = max(1, env_int("MAX_JSON_PAGE_SIZE", 100))
FILE_UPLOAD_MAX_MEMORY_SIZE = max(0, env_int("FILE_UPLOAD_MAX_MEMORY_MB", 2)) * 1024 * 1024
_shared_max_image_pixels = env_int("MAX_IMAGE_PIXELS", 60_000_000)
MAX_IMAGE_PIXELS = _shared_max_image_pixels or None

DATABASE_BACKEND = os.environ.get("DB_ENGINE", "mysql").strip().lower()
DB_CONN_MAX_AGE = max(0, env_int("DB_CONN_MAX_AGE", 30))

if DATABASE_BACKEND in {"sqlite", "sqlite3"}:
    sqlite_path = Path(
        os.environ.get("SQLITE_PATH", BASE_DIR.parent / "data" / "db.sqlite3")
    ).expanduser()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(sqlite_path),
            "CONN_MAX_AGE": 0,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", ""),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
            "OPTIONS": {
                "charset": os.environ.get("DB_CHARSET", "utf8mb4"),
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", SECURE_BY_DEFAULT)
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", SECURE_BY_DEFAULT)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = max(0, env_int("SECURE_HSTS_SECONDS", 2_592_000 if SECURE_BY_DEFAULT else 0))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", SECURE_BY_DEFAULT)
SECURE_REFERRER_POLICY = os.environ.get("SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "DENY")
USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = None
