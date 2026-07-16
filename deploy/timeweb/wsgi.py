"""WSGI-входная точка для Apache + mod_wsgi на shared-хостинге Timeweb.

Копируется в public_html/wsgi.py. В отличие от config/wsgi.py она сама
активирует виртуальное окружение и выбирает shared-профиль настроек, потому
что mod_wsgi запускает интерпретатор системы, а не из venv.

Путь к venv определяется автоматически (../venv рядом с public_html); при
нестандартном размещении задайте его через переменную TIMEWEB_VENV.
"""

import os
import site
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent  # .../public_html

# --- Активация виртуального окружения --------------------------------------
_venv = os.environ.get("TIMEWEB_VENV")
_candidates = [Path(_venv)] if _venv else []
_candidates += [PROJECT_ROOT.parent / "venv", PROJECT_ROOT / "venv"]
for _venv_path in _candidates:
    _activate = _venv_path / "bin" / "activate_this.py"
    if _activate.exists():
        exec(_activate.read_text(), {"__file__": str(_activate)})  # noqa: S102
        break
    # venv без activate_this.py — добавляем site-packages вручную
    for _sp in _venv_path.glob("lib/python*/site-packages"):
        site.addsitedir(str(_sp))
        break

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_ENV", "shared")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
