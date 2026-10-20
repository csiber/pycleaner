"""Háttérütemező: amíg a PyCleaner fut, a beállított időközönként tisztít."""

import threading
from datetime import datetime, timedelta

from . import store

_stop = threading.Event()
_thread: threading.Thread | None = None


def due(s: dict, now: datetime | None = None) -> bool:
    if not s.get("enabled"):
        return False
    last = s.get("last_run")
    if not last:
        return True
    try:
        return (now or datetime.now()) - datetime.fromisoformat(last) >= timedelta(hours=s.get("interval_hours", 24))
    except ValueError:
        return True


def _worker():
    from . import cleaner
    while not _stop.is_set():
        s = store.load_schedule()
        if due(s):
            try:
                cleaner.clean(s.get("categories", []), auto=True)
            finally:
                store.save_schedule({"last_run": store.now_iso()})
        _stop.wait(300)


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_worker, name="pycleaner-scheduler", daemon=True)
    _thread.start()


def stop():
    _stop.set()


# ── Windows Feladatütemező: tisztítás zárt programmal is ─────────────────────

TASK_PATH = "\\PyCleaner\\"
TASK_NAME = "ScheduledClean"


def task_command() -> tuple[str, str]:
    """(program, argumentumok) az ütemezett futáshoz: az exe, vagy forrásból a pythonw + main.py."""
    import os
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable, "--auto-clean"
    from .paths import resource_dir
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    main = os.path.join(os.path.dirname(resource_dir()), "main.py")
    return (pyw if os.path.exists(pyw) else exe), f'"{main}" --auto-clean'


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def register_task(interval_hours: int) -> tuple[bool, str]:
    from . import winapi
    from .i18n import t
    if not winapi.IS_WINDOWS:
        return False, t("Csak Windowson érhető el.")
    exe, args = task_command()
    hours = max(1, min(24 * 30, int(interval_hours)))
    script = (
        f"$a = New-ScheduledTaskAction -Execute {_ps_quote(exe)} -Argument {_ps_quote(args)};"
        f"$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Hours {hours});"
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew;"
        f"Register-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} -TaskPath {_ps_quote(TASK_PATH)} -Action $a -Trigger $t "
        "-Settings $s -Description 'PyCleaner: ütemezett tisztítás (github.com/csiber/pycleaner)' -Force -ErrorAction Stop | Out-Null; 'OK'")
    r = winapi.powershell(script, timeout=60)
    if "OK" in r.stdout:
        return True, t("Feladatütemező: bekapcsolva")
    return False, (r.stderr.strip().splitlines() or [t("Ismeretlen hiba.")])[0]


def unregister_task() -> tuple[bool, str]:
    from . import winapi
    from .i18n import t
    if not winapi.IS_WINDOWS:
        return True, ""
    # a feladat törlése után az üresen maradt \PyCleaner mappát is eltávolítjuk
    r = winapi.powershell(f"Unregister-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} -TaskPath {_ps_quote(TASK_PATH)} "
                          "-Confirm:$false -ErrorAction SilentlyContinue;"
                          "try { $s = New-Object -ComObject Schedule.Service; $s.Connect(); $f = $s.GetFolder('\\PyCleaner');"
                          " if ($f.GetTasks(1).Count -eq 0 -and $f.GetFolders(0).Count -eq 0) { $s.GetFolder('\\').DeleteFolder('PyCleaner', 0) } } catch {}; 'OK'",
                          timeout=60)
    return "OK" in r.stdout, t("Feladatütemező: kikapcsolva")


def task_status() -> dict:
    import json

    from . import winapi
    if not winapi.IS_WINDOWS:
        return {"supported": False}
    r = winapi.powershell(
        f"$x = Get-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} -TaskPath {_ps_quote(TASK_PATH)} -ErrorAction SilentlyContinue;"
        "if ($x) { $i = $x | Get-ScheduledTaskInfo; @{ exists = $true; state = [string]$x.State;"
        " last = if ($i.LastRunTime.Year -gt 2000) { $i.LastRunTime.ToString('s') } else { '' };"
        " next = if ($i.NextRunTime) { $i.NextRunTime.ToString('s') } else { '' }; result = $i.LastTaskResult;"
        " command = $x.Actions[0].Execute } | ConvertTo-Json -Compress } else { '{\"exists\":false}' }", timeout=60)
    try:
        st = json.loads(r.stdout.strip() or "{}")
    except ValueError:
        st = {"exists": False}
    st["supported"] = True
    exe, _args = task_command()
    st["stale"] = bool(st.get("exists") and st.get("command") and st["command"].lower() != exe.lower())
    return st


def auto_clean() -> int:
    """A Feladatütemező hívja (--auto-clean): ablak nélkül tisztít, ha esedékes, és kilép."""
    import logging
    from datetime import datetime as _dt

    from . import cleaner
    log = logging.getLogger("pycleaner.auto")
    s = store.load_schedule()
    if not s.get("enabled"):
        log.info("ütemezett tisztítás: kikapcsolva, kilépés")
        return 0
    # a beállított időköz 10%-ánál korábban nem fut újra (pl. ha közben a nyitott program már tisztított)
    if s.get("last_run"):
        try:
            if _dt.now() - _dt.fromisoformat(s["last_run"]) < timedelta(hours=s.get("interval_hours", 24) * 0.9):
                log.info("ütemezett tisztítás: nem esedékes (utolsó: %s)", s["last_run"])
                return 0
        except ValueError:
            pass
    entry = cleaner.clean(s.get("categories", []), auto=True)
    store.save_schedule({"last_run": store.now_iso()})
    log.info("ütemezett tisztítás kész: %s, %s fájl", entry["total_freed"], entry["total_files"])
    return 0
