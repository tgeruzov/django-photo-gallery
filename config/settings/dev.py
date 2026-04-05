from .base import *  # noqa: F401,F403

DEBUG = env_bool("DEBUG", True)

if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
