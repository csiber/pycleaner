"""Windows-rendszerleíró adatbázis: elavult bejegyzések keresése és javítása.

Minden módosítás előtt a teljes érintett kulcsról .reg-mentés készül
(%LOCALAPPDATA%\\PyCleaner\\registry-backups), amely dupla kattintással visszaállítható.
"""

import os
import re
from datetime import datetime

from . import winapi
from .paths import SYSTEM, registry_backups_dir

UNINSTALL_KEYS = (
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
)
RUN_KEYS = (
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
)
MUI_KEY = ("HKCU", r"SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache")

_EXE_RE = re.compile(r"\.(exe|com|bat|cmd|lnk|vbs|ps1)$", re.I)


def command_executable(cmd: str) -> str | None:
    """Egy parancssorból kinyeri a futtatható fájl útvonalát.

    Kezeli az idézőjeles, a szóközt tartalmazó idézőjel nélküli (C:\\Program Files\\x\\a.exe /b)
    és a környezeti változós (%ProgramFiles%\\…) formát. None, ha nem állapítható meg biztosan
    (pl. rundll32-paraméter vagy puszta parancsnév) — ilyenkor nem jelezzük hibásnak.
    """
    cmd = os.path.expandvars((cmd or "").strip())
    if not cmd:
        return None
    if cmd.startswith('"'):
        end = cmd.find('"', 1)
        return cmd[1:end] if end > 1 else None
    tokens = cmd.split(" ")
    for i in range(len(tokens), 0, -1):  # a leghosszabb, .exe-re végződő előtag
        cand = " ".join(tokens[:i]).rstrip(",")
        if _EXE_RE.search(cand):
            return cand
    return None


def _looks_absolute(p: str) -> bool:
    return bool(re.match(r"^[a-zA-Z]:\\", p))


def _hive(name):
    import winreg
    return {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[name]


def _values(key):
    import winreg
    i = 0
    while True:
        try:
            yield winreg.EnumValue(key, i)
        except OSError:
            return
        i += 1


def _subkeys(key):
    import winreg
    i = 0
    while True:
        try:
            yield winreg.EnumKey(key, i)
        except OSError:
            return
        i += 1


def _q(key, name):
    import winreg
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def scan() -> list[dict]:
    if SYSTEM != "Windows":
        return []
    import winreg
    issues: list[dict] = []

    # 1) eltávolítóbejegyzés, ahol a telepítési mappa ÉS az eltávolító is hiányzik
    for hive, path in UNINSTALL_KEYS:
        try:
            root = winreg.OpenKey(_hive(hive), path)
        except OSError:
            continue
        with root:
            for sub in list(_subkeys(root)):
                try:
                    with winreg.OpenKey(root, sub) as k:
                        loc = _q(k, "InstallLocation")
                        uninst = _q(k, "UninstallString")
                        name = _q(k, "DisplayName") or sub
                        if _q(k, "SystemComponent") == 1:
                            continue
                except OSError:
                    continue
                if not loc or not isinstance(loc, str):
                    continue
                loc = os.path.expandvars(loc.strip().strip('"'))
                exe = command_executable(uninst) if isinstance(uninst, str) else None
                if (_looks_absolute(loc) and not os.path.exists(loc)
                        and exe and _looks_absolute(exe) and not os.path.exists(exe)):
                    issues.append({"type": "uninstall", "hive": hive, "key": f"{path}\\{sub}", "value": None,
                                   "title": f"Árva eltávolító-bejegyzés: {name}",
                                   "detail": f"Hiányzó mappa: {loc}", "admin": hive == "HKLM"})

    # 2) automatikus indítás nem létező programra
    for hive, path in RUN_KEYS:
        try:
            k = winreg.OpenKey(_hive(hive), path)
        except OSError:
            continue
        with k:
            for name, value, _t in list(_values(k)):
                exe = command_executable(value) if isinstance(value, str) else None
                if exe and _looks_absolute(exe) and not os.path.exists(exe):
                    issues.append({"type": "run", "hive": hive, "key": path, "value": name,
                                   "title": f"Indítási bejegyzés hiányzó programra: {name}",
                                   "detail": exe, "admin": hive == "HKLM"})

    # 3) MUI-gyorsítótár: már nem létező programok nevei
    hive, path = MUI_KEY
    try:
        with winreg.OpenKey(_hive(hive), path) as k:
            stale = [n for n, _v, _t in _values(k)
                     if n.endswith((".FriendlyAppName", ".ApplicationCompany"))
                     and _looks_absolute(n) and not os.path.exists(n.rsplit(".", 1)[0])]
        if stale:
            issues.append({"type": "mui", "hive": hive, "key": path, "value": None,
                           "title": f"MUI-gyorsítótár: {len(stale)} elavult programnév",
                           "detail": "Törölt programok megjelenítendő nevei", "admin": False})
    except OSError:
        pass
    for i, it in enumerate(issues):
        it["id"] = i
    return issues


def backup_key(hive: str, key: str) -> str | None:
    """reg export — a .reg fájl útvonala, vagy None, ha nem sikerült (ilyenkor NEM módosítunk)."""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", key)[-60:]
    out = registry_backups_dir() / f"{datetime.now():%Y%m%d_%H%M%S}_{hive}_{safe}.reg"
    r = winapi.run_hidden(["reg", "export", f"{hive}\\{key}", str(out), "/y"], timeout=60)
    return str(out) if r.returncode == 0 and out.exists() else None


def fix(issue: dict) -> tuple[bool, str]:
    if SYSTEM != "Windows":
        return False, "Csak Windowson érhető el."
    import winreg
    hive, key, typ = issue.get("hive"), issue.get("key", ""), issue.get("type")
    if hive not in ("HKLM", "HKCU") or typ not in ("uninstall", "run", "mui"):
        return False, "Ismeretlen bejegyzés."
    # csak a scan() által ismert kulcsokhoz nyúlunk
    allowed = {p for _h, p in UNINSTALL_KEYS} | {p for _h, p in RUN_KEYS} | {MUI_KEY[1]}
    parent = key.rsplit("\\", 1)[0] if typ == "uninstall" else key
    if parent not in allowed:
        return False, "Nem engedélyezett kulcs."
    if hive == "HKLM" and not winapi.is_admin():
        return False, "Rendszergazdai jog szükséges."
    bk = backup_key(hive, key)
    if not bk:
        return False, "A biztonsági mentés nem sikerült, ezért nem módosítottam semmit."
    try:
        if typ == "uninstall":
            p, sub = key.rsplit("\\", 1)
            with winreg.OpenKey(_hive(hive), p, 0, winreg.KEY_ALL_ACCESS) as k:
                _delete_tree(k, sub)
        elif typ == "run":
            with winreg.OpenKey(_hive(hive), key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, issue["value"])
        elif typ == "mui":
            with winreg.OpenKey(_hive(hive), key, 0, winreg.KEY_ALL_ACCESS) as k:
                stale = [n for n, _v, _t in _values(k)
                         if n.endswith((".FriendlyAppName", ".ApplicationCompany"))
                         and _looks_absolute(n) and not os.path.exists(n.rsplit(".", 1)[0])]
                for n in stale:
                    winreg.DeleteValue(k, n)
        return True, os.path.basename(bk)
    except OSError as e:
        return False, f"Hiba: {e.strerror or e}"


def _delete_tree(parent, name):
    import winreg
    with winreg.OpenKey(parent, name, 0, winreg.KEY_ALL_ACCESS) as k:
        for sub in list(_subkeys(k)):
            _delete_tree(k, sub)
    winreg.DeleteKey(parent, name)


def list_backups() -> list[dict]:
    out = []
    for p in sorted(registry_backups_dir().glob("*.reg"), reverse=True):
        st = p.stat()
        out.append({"name": p.name, "size": st.st_size,
                    "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
    return out
