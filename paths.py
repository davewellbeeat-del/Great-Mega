"""Where things live, for both 'py app.py' and the packaged GreatMega.exe."""
import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

# Templates and static files (inside the .exe bundle when packaged)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _data_dir() -> Path:
    override = os.environ.get("GREAT_MEGA_DATA")
    if override:
        return Path(override)
    if FROZEN:      # packaged app: keep your data in a stable place, wherever the .exe sits
        return Path(os.environ.get("APPDATA") or Path.home()) / "GreatMega" / "data"
    return Path(__file__).resolve().parent / "data"


DATA_DIR = _data_dir()
