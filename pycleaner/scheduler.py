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
