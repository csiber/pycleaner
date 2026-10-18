"""Élő rendszermonitor (psutil). A hálózatot másodpercenkénti sebességként adja."""

import os
import platform
import time
from datetime import datetime

from .fsutil import disk_usage, fmt
from .paths import system_drive

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


class Sampler:
    """Kapcsolatonként egy példány: a CPU% és a hálózati sebesség két mérés különbsége."""

    def __init__(self):
        self._net = None
        self._t = None
        self._procs: dict[int, "psutil.Process"] = {}
        if psutil:
            psutil.cpu_percent(None)

    def _top_processes(self, n: int = 8) -> list[dict]:
        alive = {}
        rows = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            proc = self._procs.get(p.pid, p)
            alive[p.pid] = proc
            try:
                cpu = proc.cpu_percent(None) / (psutil.cpu_count() or 1)
                rss = p.info["memory_info"].rss if p.info.get("memory_info") else 0
                if p.pid == 0 or not p.info.get("name"):
                    continue
                rows.append({"pid": p.pid, "name": p.info["name"], "cpu": round(cpu, 1),
                             "rss": rss, "rss_fmt": fmt(rss)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._procs = alive
        rows.sort(key=lambda r: r["rss"], reverse=True)
        return rows[:n]

    def sample(self) -> dict:
        if psutil is None:
            return {"error": "A psutil nincs telepítve.", "ts": datetime.now().strftime("%H:%M:%S")}
        now = time.time()
        net = psutil.net_io_counters()
        up = down = 0.0
        if self._net and self._t:
            dt = max(0.001, now - self._t)
            up = (net.bytes_sent - self._net.bytes_sent) / dt
            down = (net.bytes_recv - self._net.bytes_recv) / dt
        self._net, self._t = net, now
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = disk_usage(system_drive())
        return {
            "cpu": psutil.cpu_percent(None),
            "cpu_count": psutil.cpu_count(),
            "ram_pct": mem.percent, "ram_used": fmt(mem.used), "ram_total": fmt(mem.total),
            "ram_available": fmt(mem.available),
            "swap_pct": swap.percent, "swap_used": fmt(swap.used), "swap_total": fmt(swap.total),
            "disk_pct": disk.get("used_pct", 0), "disk_free": disk.get("free_fmt", "—"),
            "net_up": up, "net_down": down, "net_up_fmt": fmt(up) + "/s", "net_down_fmt": fmt(down) + "/s",
            "net_sent_total": fmt(net.bytes_sent), "net_recv_total": fmt(net.bytes_recv),
            "processes": self._top_processes(),
            "ts": datetime.now().strftime("%H:%M:%S"),
        }


def system_info() -> dict:
    from . import __version__, winapi
    info = {
        "app_version": __version__,
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "processor": (platform.processor() or platform.machine())[:60],
        "is_admin": winapi.is_admin(),
        "is_windows": winapi.IS_WINDOWS,
        "has_psutil": psutil is not None,
        "disk": disk_usage(system_drive()),
        "drive": system_drive(),
    }
    if winapi.IS_WINDOWS:
        try:
            build = int(platform.version().split(".")[2])
            info["os"] = f"Windows {'11' if build >= 22000 else platform.release()} (build {build})"
        except (IndexError, ValueError):
            pass
    if psutil:
        mem = psutil.virtual_memory()
        info.update({"ram_total": fmt(mem.total), "cpu_count": psutil.cpu_count(),
                     "cpu_physical": psutil.cpu_count(logical=False),
                     "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")})
        drives = []
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts or not part.fstype:
                continue
            u = disk_usage(part.mountpoint)
            if u and u.get("total", 0) > 1024 ** 3:
                drives.append({"mount": part.mountpoint, "fstype": part.fstype, **u})
        info["drives"] = drives[:12]
    info["pid"] = os.getpid()
    return info
