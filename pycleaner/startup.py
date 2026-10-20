"""Indítópult-kezelő: bejelentkezéskor induló programok listája és ki/be kapcsolása.

A kikapcsolás ugyanúgy történik, mint a Windows Feladatkezelőjében: a bejegyzés megmarad,
csak a StartupApproved kulcsban kap „letiltva” jelzőt (páratlan első bájt). Ütemezett
feladatnál a Feladatütemező saját engedélyezés/letiltás funkcióját használjuk.
"""

import json
import os
import struct
import time

from . import winapi
from .i18n import t
from .paths import SYSTEM
from .registry import command_executable

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

# forrás → (hive, kulcs, StartupApproved alkulcs)
SOURCES = {
    "run_user": ("HKCU", RUN, "Run"),
    "run_machine": ("HKLM", RUN, "Run"),
    "run_machine32": ("HKLM", RUN32, "Run32"),
}


def _hive(name):
    import winreg
    return {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[name]


def _approved_state(hive: str, sub: str, name: str) -> bool:
    """True = engedélyezett. Hiányzó jelző = engedélyezett (a Windows is így kezeli)."""
    import winreg
    try:
        with winreg.OpenKey(_hive(hive), f"{APPROVED}\\{sub}") as k:
            data, _t = winreg.QueryValueEx(k, name)
        return not (bytes(data)[:1] and bytes(data)[0] & 1)
    except OSError:
        return True


def approved_blob(enabled: bool, now: float | None = None) -> bytes:
    """A Feladatkezelő formátuma: 4 bájt jelző + 8 bájt FILETIME (letiltáskor az időpont)."""
    if enabled:
        return b"\x02" + b"\x00" * 11
    ft = int(((now or time.time()) + 11644473600) * 10_000_000)
    return b"\x03\x00\x00\x00" + struct.pack("<Q", ft)


def _set_approved(hive: str, sub: str, name: str, enabled: bool) -> None:
    import winreg
    with winreg.CreateKeyEx(_hive(hive), f"{APPROVED}\\{sub}", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, approved_blob(enabled))


def _folders():
    appdata, progdata = os.environ.get("APPDATA", ""), os.environ.get("ProgramData", "")
    return [("folder_user", "HKCU", os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")),
            ("folder_common", "HKLM", os.path.join(progdata, r"Microsoft\Windows\Start Menu\Programs\StartUp"))]


_PS_EXTRA = r"""
$out = @{ lnk = @{}; tasks = @() }
$sh = New-Object -ComObject WScript.Shell
foreach ($p in $lnks) { try { $out.lnk[$p] = $sh.CreateShortcut($p).TargetPath } catch {} }
$out.tasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $_.TaskPath -notlike '\Microsoft\*' -and ($_.Triggers | Where-Object { $_.CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger' })
  } | ForEach-Object {
    $a = $_.Actions | Select-Object -First 1
    @{ name = $_.TaskName; path = $_.TaskPath; state = [int]$_.State; exe = $a.Execute; args = $a.Arguments; author = $_.Author }
  })
$out | ConvertTo-Json -Depth 4 -Compress
"""


def _extra(lnks: list[str]) -> dict:
    quoted = ",".join("'" + p.replace("'", "''") + "'" for p in lnks)
    r = winapi.powershell(f"$lnks = @({quoted});" + _PS_EXTRA, timeout=90)
    try:
        return json.loads(r.stdout.strip() or "{}")
    except ValueError:
        return {}


def list_items() -> list[dict]:
    if SYSTEM != "Windows":
        return []
    import winreg
    items: list[dict] = []
    for src, (hive, key, sub) in SOURCES.items():
        try:
            k = winreg.OpenKey(_hive(hive), key)
        except OSError:
            continue
        with k:
            i = 0
            while True:
                try:
                    name, value, _t = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                if not isinstance(value, str):
                    continue
                exe = command_executable(value) or ""
                items.append({"source": src, "hive": hive, "name": name, "command": value, "exe": exe,
                              "enabled": _approved_state(hive, sub, name)})
    lnks = []
    for src, hive, folder in _folders():
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if fn.lower() == "desktop.ini":
                continue
            fp = os.path.join(folder, fn)
            if fn.lower().endswith(".lnk"):
                lnks.append(fp)
            items.append({"source": src, "hive": hive, "name": os.path.splitext(fn)[0], "file": fn, "command": fp,
                          "exe": fp, "enabled": _approved_state(hive, "StartupFolder", fn)})
    extra = _extra(lnks)
    targets = extra.get("lnk") or {}
    for it in items:
        if it["exe"] in targets and targets[it["exe"]]:
            it["exe"] = it["command"] = targets[it["exe"]]
    for tk in extra.get("tasks") or []:
        items.append({"source": "task", "hive": "HKLM", "name": tk.get("name", ""), "task_path": tk.get("path", "\\"),
                      "command": f"{tk.get('exe') or ''} {tk.get('args') or ''}".strip(),
                      "exe": os.path.expandvars((tk.get("exe") or "").strip('"')), "enabled": tk.get("state") != 1,
                      "author": tk.get("author") or ""})
    admin = winapi.is_admin()
    for n, it in enumerate(items):
        it["id"] = n
        it["publisher"] = winapi.file_company(it["exe"]) or it.get("author", "")
        it["missing"] = bool(it["exe"]) and os.path.isabs(it["exe"]) and not os.path.exists(it["exe"])
        it["admin"] = it["hive"] == "HKLM"
        it["locked"] = it["admin"] and not admin
        it["kind"] = {"task": t("Ütemezett feladat"), "folder_user": t("Indítópult mappa"),
                      "folder_common": t("Indítópult mappa (minden felhasználó)")}.get(it["source"], t("Registry (Run)"))
    items.sort(key=lambda x: (not x["enabled"], x["name"].lower()))
    return items


def set_enabled(item: dict, enabled: bool) -> tuple[bool, str]:
    if SYSTEM != "Windows":
        return False, t("Csak Windowson érhető el.")
    if item.get("hive") == "HKLM" and not winapi.is_admin():
        return False, t("Rendszergazdai jog szükséges.")
    try:
        src = item["source"]
        if src in SOURCES:
            hive, _key, sub = SOURCES[src]
            _set_approved(hive, sub, item["name"], enabled)
        elif src in ("folder_user", "folder_common"):
            _set_approved(item["hive"], "StartupFolder", item["file"], enabled)
        elif src == "task":
            verb = "Enable" if enabled else "Disable"
            name = item["name"].replace("'", "''")
            path = item.get("task_path", "\\").replace("'", "''")
            r = winapi.powershell(f"{verb}-ScheduledTask -TaskName '{name}' -TaskPath '{path}' -ErrorAction Stop | Out-Null",
                                  timeout=60)
            if r.returncode != 0:
                return False, (r.stderr.strip().splitlines() or [t("Ismeretlen hiba.")])[0]
        else:
            return False, t("Ismeretlen bejegyzés.")
        return True, t("Bekapcsolva") if enabled else t("Kikapcsolva")
    except OSError as e:
        return False, t("Hiba: {e}", e=e.strerror or e)
