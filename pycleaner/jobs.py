"""Háttérmunkák (winget-frissítés, program-eltávolítás): a felület lekérdezi az állapotukat."""

import threading
import time
import uuid

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def start(kind: str, title: str, fn, *args) -> str:
    """fn(job, *args) egy külön szálon fut; a job['log']-ba írhat, a visszatérési értéke a result."""
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "kind": kind, "title": title, "status": "running", "log": [], "result": None,
           "error": "", "started": time.time(), "finished": None}
    with _lock:
        _jobs[jid] = job
        # a régi, befejezett munkák ne gyűljenek a végtelenségig
        done = sorted((j for j in _jobs.values() if j["finished"]), key=lambda j: j["finished"])
        for old in done[:-50]:
            _jobs.pop(old["id"], None)

    def run():
        try:
            job["result"] = fn(job, *args)
            job["status"] = "done"
        except Exception as e:  # noqa: BLE001 — a hibát a felület mutatja meg
            job["status"] = "error"
            job["error"] = str(e)[:500]
        finally:
            job["finished"] = time.time()

    threading.Thread(target=run, name=f"job-{kind}", daemon=True).start()
    return jid


def get(jid: str) -> dict | None:
    with _lock:
        j = _jobs.get(jid)
        return dict(j, log=list(j["log"][-200:])) if j else None


def running(kind: str | None = None) -> list[dict]:
    with _lock:
        return [dict(j, log=[]) for j in _jobs.values() if j["status"] == "running" and (kind is None or j["kind"] == kind)]
