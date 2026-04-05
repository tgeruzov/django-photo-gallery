import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("TIMEWEB_PROJECT_ROOT", Path(__file__).resolve().parent)).expanduser()


def activate_virtualenv():
    candidates = []

    if "TIMEWEB_VENV_ACTIVATE" in os.environ:
        candidates.append(Path(os.environ["TIMEWEB_VENV_ACTIVATE"]).expanduser())

    candidates.extend(
        [
            PROJECT_ROOT.parent / "venv" / "bin" / "activate_this.py",
            PROJECT_ROOT.parent / ".venv" / "bin" / "activate_this.py",
        ]
    )

    for activate_script in candidates:
        if activate_script.exists():
            exec(activate_script.read_text(), {"__file__": str(activate_script)})
            return


activate_virtualenv()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Timeweb documents a significant SQLite slowdown on Python 3.10 + mod_wsgi.
if os.environ.get("DB_ENGINE", "mysql").strip().lower() in {"sqlite", "sqlite3"}:
    try:
        __import__("pysqlite3")
    except ImportError:
        pass
    else:
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

os.environ.setdefault("DJANGO_ENV", "shared")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_shared")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
