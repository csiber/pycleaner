"""Vékony Windows API-réteg (ctypes). Más rendszeren minden függvény ártalmatlan no-op."""

import ctypes
import os
import subprocess
import sys

from .paths import SYSTEM

IS_WINDOWS = SYSTEM == "Windows"
CREATE_NO_WINDOW = 0x08000000


def is_admin() -> bool:
    if IS_WINDOWS:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def relaunch_elevated() -> bool:
    """Újraindítás rendszergazdaként (UAC-ablak). True, ha az új példány elindult."""
    if not IS_WINDOWS:
        return False
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, subprocess.list2cmdline(sys.argv[1:])
    else:
        exe, params = sys.executable, subprocess.list2cmdline(["-m", "pycleaner", *sys.argv[1:]])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def run_hidden(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Parancs futtatása konzolablak felvillanása nélkül."""
    kw = {"creationflags": CREATE_NO_WINDOW} if IS_WINDOWS else {}
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace", **kw)


def powershell(script: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return run_hidden(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + script], timeout)


# ── Lomtár ────────────────────────────────────────────────────────────────────

class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]


def recycle_bin_info():
    """(bájt, elemszám) az összes meghajtó Lomtárára."""
    if not IS_WINDOWS:
        return 0, 0
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return 0, 0
    return int(info.i64Size), int(info.i64NumItems)


def empty_recycle_bin() -> bool:
    if not IS_WINDOWS:
        return False
    # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
    return hr in (0, -2147418113)  # S_OK, vagy E_UNEXPECTED, ha már üres volt


# ── Fájlkezelő ────────────────────────────────────────────────────────────────

def reveal(path: str) -> bool:
    """A fájl megmutatása a rendszer fájlkezelőjében."""
    try:
        if IS_WINDOWS:
            subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(path)])
        elif SYSTEM == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path) or "/"])
        return True
    except OSError:
        return False


# ── Visszaállítási pont ──────────────────────────────────────────────────────

def create_restore_point(description: str = "PyCleaner") -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Csak Windowson érhető el."
    if not is_admin():
        return False, "Rendszergazdai jog szükséges."
    desc = description.replace("'", "")
    r = powershell(
        "Enable-ComputerRestore -Drive \"$env:SystemDrive\\\" -ErrorAction SilentlyContinue;"
        f"Checkpoint-Computer -Description '{desc}' -RestorePointType MODIFY_SETTINGS "
        "-ErrorAction Stop -WarningVariable w -WarningAction SilentlyContinue; if ($w) { 'PYC_SKIPPED' }",
        timeout=300)
    if r.returncode == 0 and "PYC_SKIPPED" in r.stdout:
        # alapból a Windows 24 óránként csak egy pontot enged — nem hiba, de nem is új pont
        return True, "Az elmúlt 24 órában már készült visszaállítási pont, a Windows nem hozott létre újat."
    if r.returncode == 0:
        return True, "Visszaállítási pont létrehozva."
    msg = (r.stderr or r.stdout).strip().splitlines()
    return False, msg[0] if msg else "Ismeretlen hiba."
