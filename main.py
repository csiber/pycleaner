"""Indító szkript forrásból futtatáshoz és a PyInstaller-buildhez: python main.py"""

import importlib.util
import os
import subprocess
import sys

# modulnév → pip-csomagnév; a pywebview opcionális (nélküle böngészőben nyílik)
REQUIRED = {"flask": "flask", "psutil": "psutil", "send2trash": "send2trash"}


def ensure_dependencies() -> None:
    """Forrásból indításnál érthető üzenet hiányzó csomagokra, és felajánlja a telepítést."""
    if getattr(sys, "frozen", False):
        return  # az exe mindent tartalmaz
    missing = [pkg for mod, pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    req = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    print("A PyCleaner forrásból indításához hiányzó Python-csomagok:", ", ".join(missing))
    print(f"Telepítés kézzel:  {sys.executable} -m pip install -r \"{req}\"")
    print("(Ha nem akarsz Pythonnal foglalkozni, töltsd le a kész programot:")
    print(" https://github.com/csiber/pycleaner/releases/latest)\n")
    if not sys.stdin or not sys.stdin.isatty():
        sys.exit(1)
    if input("Telepítsem most? [I/n] ").strip().lower() not in ("", "i", "igen", "y", "yes"):
        sys.exit(1)
    rc = subprocess.call([sys.executable, "-m", "pip", "install", "-r", req])
    if rc != 0:
        input("A telepítés nem sikerült. Nyomj Entert a kilépéshez…")
        sys.exit(rc)
    importlib.invalidate_caches()


if __name__ == "__main__":
    ensure_dependencies()
    from pycleaner.launcher import main

    main()
