import os

DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()

if DJANGO_ENV in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
elif DJANGO_ENV == "shared":
    from .shared import *  # noqa: F401,F403
elif DJANGO_ENV == "test":
    from .test import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
