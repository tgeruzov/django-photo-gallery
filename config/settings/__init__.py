import os
from pathlib import Path

from dotenv import load_dotenv

# .env читается до выбора профиля, иначе DJANGO_ENV из него игнорируется
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Без явного DJANGO_ENV поднимается prod: забытое окружение на сервере должно
# падать на проверке SECRET_KEY, а не молча стартовать с DEBUG=True.
DJANGO_ENV = os.getenv("DJANGO_ENV", "prod").strip().lower()

if DJANGO_ENV in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
elif DJANGO_ENV == "test":
    from .test import *  # noqa: F401,F403
elif DJANGO_ENV == "dev":
    from .dev import *  # noqa: F401,F403
else:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(f"Unknown DJANGO_ENV={DJANGO_ENV!r}: expected dev, test or prod.")
