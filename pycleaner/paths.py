"""Erőforrás- és adatkönyvtárak feloldása (forrásból és PyInstaller-exe-ből is)."""

import os
import platform
import sys
from pathlib import Path

SYSTEM = platform.system()


def resource_dir() -> Path:
    """A csomag sablonjai és statikus fájljai (exe-ben a kicsomagolt _MEIPASS alatt)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "pycleaner"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Tartós adatok helye: beállítások, előzmények, mentések.

    Sorrend: PYCLEANER_DATA környezeti változó → hordozható mód (portable.txt az exe
    mellett) → a rendszer szokásos felhasználói adatmappája.
    """
    override = os.environ.get("PYCLEANER_DATA", "").strip().strip('"')
    if override:
        base = Path(override)
    elif getattr(sys, "frozen", False) and (Path(sys.executable).parent / "portable.txt").exists():
        base = Path(sys.executable).parent / "PyCleanerData"
    elif SYSTEM == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PyCleaner"
    elif SYSTEM == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "PyCleaner"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "pycleaner"
    base.mkdir(parents=True, exist_ok=True)
    return base


def backups_dir() -> Path:
    p = data_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def registry_backups_dir() -> Path:
    p = data_dir() / "registry-backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def system_drive() -> str:
    if SYSTEM == "Windows":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"
