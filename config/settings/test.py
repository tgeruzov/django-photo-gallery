from .dev import *  # noqa: F401,F403

# Быстрые и герметичные тесты: слабый hasher, eager celery,
# файлы по умолчанию в памяти (тестовый класс может переопределить).
DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
ENABLE_BACKGROUND_TASKS = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# cache_page не должен отдавать ответы одного теста другому
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
