import os
import sys

DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()
IS_TEST_COMMAND = len(sys.argv) > 1 and sys.argv[1] == "test"

if IS_TEST_COMMAND or DJANGO_ENV == "test":
    from .test import *  # noqa: F401,F403
elif DJANGO_ENV in {"shared", "timeweb", "timeweb-shared", "timeweb_shared"}:
    from ..settings_shared import *  # noqa: F401,F403
elif DJANGO_ENV in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
