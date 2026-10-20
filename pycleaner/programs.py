"""Telepített programok listája, eltávolítás a program saját eltávolítójával, maradékkeresés."""

import os
import re
import shlex
import subprocess
import time

from . import winapi
from .fsutil import dir_size, fmt
from .i18n import t
from .paths import SYSTEM

UNINSTALL = (
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
)
# ezek nevű mappát soha nem ajánlunk maradékként, mert több program közös mappája
GENERIC = {"microsoft", "google", "mozilla", "adobe", "apple", "intel", "nvidia", "amd", "common files", "windows",
           "packages", "programs", "temp", "microsoft shared", "windowsapps", "installer", "package cache",
           "steam", "epic games", "oracle", "java", "python", "jetbrains", "github", "unity", "autodesk"}


def _hive(name):
    import winreg
    return {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[name]


def _q(k, name):
    import winreg
    try:
        return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _date(v) -> str:
    v = str(v or "")
    if re.fullmatch(r"\d{8}", v):
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return ""


def list_programs() -> list[dict]:
    if SYSTEM != "Windows":
        return []
    import winreg
    out, seen = [], set()
    for hive, path in UNINSTALL:
        try:
            root = winreg.OpenKey(_hive(hive), path)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        name = _q(k, "DisplayName")
                        uninst = _q(k, "UninstallString")
                        if (not name or not uninst or _q(k, "SystemComponent") == 1 or _q(k, "ParentKeyName")
                                or str(_q(k, "ReleaseType") or "").lower() in ("update", "hotfix", "security update")):
                            continue
                        size_kb = _q(k, "EstimatedSize")
                        item = {"key": f"{hive}\\{path}\\{sub}", "hive": hive, "name": str(name).strip(),
                                "publisher": str(_q(k, "Publisher") or "").strip(),
                                "version": str(_q(k, "DisplayVersion") or "").strip(),
                                "installed": _date(_q(k, "InstallDate")),
                                "size": int(size_kb) * 1024 if isinstance(size_kb, int) else 0,
                                "location": str(_q(k, "InstallLocation") or "").strip().strip('"'),
                                "uninstall": str(uninst), "quiet": str(_q(k, "QuietUninstallString") or ""),
                                "msi": str(uninst).lower().startswith("msiexec")}
                except OSError:
                    continue
                dedup = (item["name"].lower(), item["version"])
                if dedup in seen:
                    continue
                seen.add(dedup)
                item["size_fmt"] = fmt(item["size"]) if item["size"] else ""
                out.append(item)
    out.sort(key=lambda x: x["name"].lower())
    for n, it in enumerate(out):
        it["id"] = n
    return out


def uninstall_command(item: dict) -> list[str] | str:
    """Az eltávolító parancsa. MSI-nél /I helyett /X (a regisztrált /I a „módosítás” párbeszédet nyitná)."""
    cmd = item["uninstall"].strip()
    if item.get("msi"):
        m = re.search(r"\{[0-9A-Fa-f\-]{36}\}", cmd)
        if m:
            return ["msiexec.exe", "/x", m.group(0)]
    return cmd  # a Windows is így futtatja: CreateProcess a regisztrált parancssorral


def _key_exists(full_key: str) -> bool:
    import winreg
    hive, rest = full_key.split("\\", 1)
    try:
        winreg.OpenKey(_hive(hive), rest).Close()
        return True
    except OSError:
        return False


def leftovers(item: dict) -> list[dict]:
    """Eltávolítás utáni maradékok: a telepítési mappa, és a pontosan a program nevét viselő
    AppData/ProgramData-mappák. Általános (gyártói, közös) nevet soha nem javasol."""
    from .cleaner import is_protected
    cands = []
    loc = item.get("location", "")
    if loc and os.path.isdir(loc):
        cands.append(loc)
    base = re.sub(r"\s*[\(\[].*?[\)\]]", "", item["name"])           # „(x64)”, „[64 bit]”
    base = re.sub(r"\s+v?\d+(\.\d+)+.*$", "", base).strip()          # verziószám a végén
    names = {base}
    if item.get("publisher"):
        names.add(os.path.join(item["publisher"].split(",")[0].strip(), base))
    roots = [os.environ.get(v, "") for v in ("APPDATA", "LOCALAPPDATA", "ProgramData")]
    roots += [os.environ.get(v, "") for v in ("ProgramFiles", "ProgramFiles(x86)")]
    for r in filter(None, roots):
        for n in names:
            if len(os.path.basename(n)) < 4 or os.path.basename(n).lower() in GENERIC:
                continue
            p = os.path.join(r, n)
            if os.path.isdir(p):
                cands.append(p)
    out, seen = [], set()
    for p in cands:
        key = os.path.normcase(os.path.abspath(p))
        if key in seen or is_protected(p) or os.path.basename(p).lower() in GENERIC:
            continue
        seen.add(key)
        size, files = dir_size(p)
        out.append({"path": p, "size": size, "size_fmt": fmt(size), "files": files})
    return out


def run_uninstall(job: dict, item: dict) -> dict:
    cmd = uninstall_command(item)
    job["log"].append(t("Eltávolító indítása: {name}", name=item["name"]))
    job["log"].append("   " + (cmd if isinstance(cmd, str) else " ".join(shlex.quote(c) for c in cmd)))
    started = time.time()
    try:
        proc = subprocess.Popen(cmd)  # látható ablak: a felhasználó végigkattintja az eltávolítót
        rc = proc.wait(timeout=3600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e), "leftovers": []}
    # sok eltávolító egy ideiglenes példányt indít és azonnal kilép — várunk, amíg a bejegyzés eltűnik
    deadline = time.time() + 600
    while _key_exists(item["key"]) and time.time() < deadline:
        time.sleep(2)
    removed = not _key_exists(item["key"])
    job["log"].append(t("Eltávolítva.") if removed else t("A program bejegyzése megmaradt (megszakítva?)."))
    return {"ok": removed, "code": rc, "removed": removed, "seconds": round(time.time() - started),
            "leftovers": leftovers(item) if removed else []}


def remove_leftovers(paths: list[str], allowed: set[str]) -> list[dict]:
    """A felkínált maradékmappák Lomtárba helyezése (csak amit mi javasoltunk)."""
    from .fsutil import send_to_trash
    res = []
    for p in paths:
        key = os.path.normcase(os.path.abspath(p))
        if key not in allowed:
            res.append({"path": p, "ok": False, "error": t("Ezt a mappát nem a PyCleaner javasolta.")})
            continue
        try:
            send_to_trash(p)
            res.append({"path": p, "ok": True})
        except Exception as e:  # noqa: BLE001
            res.append({"path": p, "ok": False, "error": str(e)})
    return res

