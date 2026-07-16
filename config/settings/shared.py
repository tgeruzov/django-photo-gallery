"""Настройки для виртуального (shared) хостинга Timeweb.

Отличия от prod.py: приложение работает под Apache + mod_wsgi (не gunicorn),
без Redis и Celery-воркеров, статику раздаёт сам Apache через .htaccess,
поэтому whitenoise и manifest-хранилище здесь не используются. База — MySQL
(единственный доступный на тарифе сервер БД) либо SQLite.

Профиль активируется переменной окружения DJANGO_ENV=shared.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

# --- Секреты ---------------------------------------------------------------
# Как и в prod: отказываемся стартовать с дефолтным/слабым ключом.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if (
    not SECRET_KEY
    or SECRET_KEY == "dev-key-change-in-production"  # noqa: S105 — это dev-дефолт, не секрет
    or len(SECRET_KEY) < 50
):
    raise ImproperlyConfigured("SECRET_KEY must be set to a strong unique value in production.")

DEBUG = env_bool("DEBUG", False)

# --- Статика и медиа -------------------------------------------------------
# Apache отдаёт /static/ из STATIC_ROOT (правило в .htaccess) и /media/
# напрямую с диска. Оставляем простое FileSystem/StaticFiles-хранилище из
# base (без whitenoise и без хешей в именах) — так collectstatic кладёт файлы
# под исходными именами, а mod_wsgi-процессу не нужно раздавать статику.

# --- Кэш -------------------------------------------------------------------
# Redis на тарифе нет — остаётся LocMemCache из base.

# --- Фоновые задачи --------------------------------------------------------
# Долгоживущих воркеров на shared-хостинге нет: варианты изображений
# генерируются синхронно в запросе (eager), периодический backfill не нужен.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", False)

# --- Безопасность ----------------------------------------------------------
# Сайт обслуживается по HTTPS (сертификат + редирект настроены в панели/.htaccess).
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
SESSION_COOKIE_SAMESITE = "Strict"
SECURE_CONTENT_TYPE_NOSNIFF = True

# Редирект на HTTPS уже делает панель Timeweb / .htaccess. Включать Django-редирект
# по умолчанию НЕ будем: под mod_wsgi это легко даёт петлю, если приложение видит
# запрос как http. При необходимости включается через окружение.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)

# Если TLS терминируется на фронтенде и mod_wsgi отдаёт http, включите
# USE_FORWARDED_PROTO=1 — тогда Django будет доверять X-Forwarded-Proto
# (нужно для secure-cookies и CSRF, иначе логин в админку может не работать).
if env_bool("USE_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS — только когда HTTPS стабилен; по умолчанию выключен (0), включается env.
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
