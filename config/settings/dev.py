from .base import *  # noqa: F401,F403

DEBUG = env_bool("DEBUG", True)

if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", True)
