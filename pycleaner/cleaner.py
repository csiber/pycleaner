"""Tisztítási kategóriák, beolvasás és tisztítás.

Minden kategória „célokból” áll: egy mappa + szabályok (minimum kor, kiterjesztés-szűrő,
fájlnév-előtag). A törlés soha nem követ szimbolikus linket, és a védett mappákhoz
(meghajtógyökér, Windows, Program Files, felhasználói profil gyökere) nem nyúl.
"""

import os
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import store, winapi
from .fsutil import candidates, clean_dir, existing, expand, fmt, glob_dirs, measure
from .paths import SYSTEM, backups_dir

WIN = SYSTEM == "Windows"
MAC = SYSTEM == "Darwin"
LINUX = SYSTEM == "Linux"


@dataclass
class Target:
    path: str
    min_age: float = 0              # napokban; a felhasználói érték ennél kisebb nem lehet
    suffixes: tuple | None = None   # csak ezek a végződések
    prefix: tuple | None = None     # csak ezek az előtagok
    skip_hidden_top: bool = False   # POSIX /tmp: .X11-unix és társai maradnak


@dataclass
class Category:
    id: str
    label: str
    desc: str
    icon: str
    default: bool = True
    admin: bool = False             # rendszergazdai jog kell hozzá (Windows)
    caution: str = ""               # figyelmeztetés a felületen
    targets: list = field(default_factory=list)


# ── célmappák rendszerenként ─────────────────────────────────────────────────

def _env(name: str) -> str:
    return os.environ.get(name, "")


def _chromium_caches() -> list[str]:
    la = _env("LOCALAPPDATA")
    roots = [
        os.path.join(la, "Google", "Chrome", "User Data"),
        os.path.join(la, "Microsoft", "Edge", "User Data"),
        os.path.join(la, "BraveSoftware", "Brave-Browser", "User Data"),
        os.path.join(la, "Vivaldi", "User Data"),
        os.path.join(_env("APPDATA"), "Opera Software", "Opera Stable"),
    ]
    out = []
    for root in roots:
        for sub in (("Cache",), ("Code Cache",), ("GPUCache",)):
            out += glob_dirs(root, *sub)            # Default, Profile 1, …
            out.append(os.path.join(root, *sub))    # Opera: közvetlenül a gyökér alatt
    return out


def _targets() -> dict[str, list[Target]]:
    home = str(Path.home())
    t: dict[str, list[Target]] = {}
    if WIN:
        la, pd, wd = _env("LOCALAPPDATA"), _env("ProgramData"), _env("WINDIR") or r"C:\Windows"
        t["temp"] = [Target(tempfile.gettempdir()), Target(os.path.join(la, "Temp")),
                     Target(os.path.join(wd, "Temp"))]
        firefox = glob_dirs(os.path.join(la, "Mozilla", "Firefox", "Profiles"), "cache2")
        t["browser"] = [Target(p) for p in _chromium_caches() + firefox]
        t["thumbnails"] = [Target(os.path.join(la, "Microsoft", "Windows", "Explorer"),
                                  suffixes=(".db",), prefix=("thumbcache_", "iconcache_"))]
        t["logs"] = [Target(os.path.join(wd, "Logs"), min_age=7, suffixes=(".log", ".old", ".bak", ".etl")),
                     Target(os.path.join(wd, "Panther"), min_age=30, suffixes=(".log",))]
        t["crash"] = [Target(os.path.join(la, "CrashDumps")),
                      Target(os.path.join(la, "Microsoft", "Windows", "WER", "ReportArchive")),
                      Target(os.path.join(la, "Microsoft", "Windows", "WER", "ReportQueue")),
                      Target(os.path.join(pd, "Microsoft", "Windows", "WER", "ReportArchive")),
                      Target(os.path.join(pd, "Microsoft", "Windows", "WER", "ReportQueue")),
                      Target(os.path.join(wd, "Minidump"))]
        t["winupdate"] = [Target(os.path.join(wd, "SoftwareDistribution", "Download"))]
        t["shader"] = [Target(os.path.join(la, "D3DSCache")),
                       Target(os.path.join(la, "NVIDIA", "DXCache")),
                       Target(os.path.join(la, "NVIDIA", "GLCache")),
                       Target(os.path.join(la, "AMD", "DxCache")),
                       Target(os.path.join(la, "AMD", "DxcCache")),
                       Target(os.path.join(la, "AMD", "VkCache"))]
    elif MAC:
        t["temp"] = [Target(tempfile.gettempdir(), min_age=1, skip_hidden_top=True)]
        lib = os.path.join(home, "Library")
        t["browser"] = [Target(os.path.join(lib, "Caches", "Google", "Chrome")),
                        Target(os.path.join(lib, "Caches", "Firefox")),
                        Target(os.path.join(lib, "Caches", "BraveSoftware")),
                        Target(os.path.join(lib, "Caches", "Microsoft Edge"))]
        t["logs"] = [Target(os.path.join(lib, "Logs"), min_age=7, suffixes=(".log", ".old"))]
        t["crash"] = [Target(os.path.join(lib, "Logs", "DiagnosticReports"))]
        t["trash"] = [Target(os.path.join(home, ".Trash"))]
    else:
        cache = _env("XDG_CACHE_HOME") or os.path.join(home, ".cache")
        t["temp"] = [Target("/tmp", min_age=1, skip_hidden_top=True),
                     Target("/var/tmp", min_age=7, skip_hidden_top=True)]
        t["browser"] = [Target(os.path.join(cache, n)) for n in
                        ("google-chrome", "chromium", "BraveSoftware", "microsoft-edge", "mozilla")]
        t["thumbnails"] = [Target(os.path.join(cache, "thumbnails")),
                           Target(os.path.join(home, ".thumbnails"))]
        t["logs"] = [Target("/var/log", suffixes=(".gz", ".old", ".1", ".xz", ".bz2"))]
        t["crash"] = [Target("/var/crash")]
        data = _env("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        t["trash"] = [Target(os.path.join(data, "Trash", "files")),
                      Target(os.path.join(data, "Trash", "info"))]
    return t


def categories() -> list[Category]:
    t = _targets()
    cats = [
        Category("temp", "Ideiglenes fájlok", "A rendszer és a programok által hátrahagyott átmeneti fájlok.",
                 "file-text", targets=t.get("temp", [])),
        Category("browser", "Böngésző-gyorsítótár",
                 "Chrome, Edge, Brave, Vivaldi, Opera és Firefox gyorsítótára. Jelszavak, előzmények, "
                 "sütik és könyvjelzők érintetlenek maradnak.", "globe", targets=t.get("browser", [])),
        Category("thumbnails", "Bélyegkép-gyorsítótár", "Az Intéző képelőnézetei; szükség szerint újraépülnek.",
                 "image", targets=t.get("thumbnails", [])),
        Category("crash", "Hibajelentések és memóriaképek", "Összeomlási dumpok és Windows-hibajelentések.",
                 "triangle-alert", targets=t.get("crash", [])),
        Category("logs", "Régi naplófájlok", "Legalább egy hetes rendszernaplók és rotált naplók.",
                 "scroll-text", default=False, admin=WIN, targets=t.get("logs", [])),
        Category("winupdate", "Windows Update gyorsítótár",
                 "Már telepített frissítések letöltött csomagjai és a kézbesítésoptimalizálás tára.",
                 "download", default=False, admin=True, targets=t.get("winupdate", [])),
        Category("shader", "Shader-gyorsítótár", "DirectX/NVIDIA/AMD shader-tár.", "zap", default=False,
                 caution="A játékok első indításkor újraépítik, ez rövid akadozással járhat.",
                 targets=t.get("shader", [])),
        Category("trash", "Lomtár", "A Lomtár végleges ürítése.", "trash-2", default=False,
                 caution="Végleges törlés — utána nem állíthatók vissza a fájlok.",
                 targets=t.get("trash", [])),
        Category("custom", "Egyéni mappák", "A Beállításokban megadott saját mappák tartalma.", "folder",
                 default=False, caution="A megadott mappák teljes tartalmát törli."),
    ]
    out = []
    for c in cats:
        if c.id == "trash" and WIN:
            out.append(c)
        elif c.id == "custom":
            c.targets = [Target(d) for d in custom_dirs()]
            out.append(c)
        elif c.targets:
            out.append(c)
    return out


CATEGORY_IDS = {"temp", "browser", "thumbnails", "crash", "logs", "winupdate", "shader", "trash", "custom"}


# ── védett mappák ────────────────────────────────────────────────────────────

def _protected() -> set[str]:
    home = str(Path.home())
    p = {home, os.path.join(home, "Desktop"), os.path.join(home, "Documents"),
         os.path.join(home, "Downloads"), os.path.join(home, "Pictures"), os.path.join(home, "Videos"),
         os.path.join(home, "Music"), "/", "/usr", "/etc", "/bin", "/home", "/var", "/opt", "/boot"}
    if WIN:
        for v in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "USERPROFILE",
                  "APPDATA", "LOCALAPPDATA", "SystemDrive", "PUBLIC"):
            if _env(v):
                p.add(_env(v))
        p.update(f"{chr(c)}:\\" for c in range(65, 91))
    return {os.path.normcase(os.path.normpath(x)) for x in p}


def is_protected(path: str) -> bool:
    norm = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    if norm in _protected():
        return True
    return os.path.dirname(norm) == norm  # bármilyen gyökér


def custom_dirs() -> list[str]:
    dirs = [expand(d) for d in store.active_profile().get("custom_dirs", [])]
    return [d for d in existing(dirs) if not is_protected(d)]


# ── beolvasás ────────────────────────────────────────────────────────────────

def _rules(tg: Target, min_age_days: float = 0) -> dict:
    return {"min_age_days": max(min_age_days, tg.min_age), "suffixes": tg.suffixes,
            "skip_hidden_top": tg.skip_hidden_top, "prefix": tg.prefix}


def _live_targets(c: Category) -> list[Target]:
    seen, out = set(), []
    for tg in c.targets:
        key = os.path.normcase(os.path.abspath(tg.path))
        if key in seen or not os.path.isdir(tg.path) or is_protected(tg.path):
            continue
        seen.add(key)
        out.append(tg)
    return out


def scan() -> dict:
    out = {}
    for c in categories():
        size = files = 0
        if c.id == "trash" and WIN:
            size, files = winapi.recycle_bin_info()
        else:
            for tg in _live_targets(c):
                s, n = measure(tg.path, **_rules(tg))
                size += s
                files += n
        out[c.id] = {"size": size, "size_fmt": fmt(size), "files": files}
    return out


def category_meta() -> list[dict]:
    admin = winapi.is_admin()
    return [{"id": c.id, "label": c.label, "desc": c.desc, "icon": c.icon, "default": c.default,
             "admin": c.admin, "locked": c.admin and not admin, "caution": c.caution,
             "paths": [t.path for t in _live_targets(c)]} for c in categories()]


BROWSER_PROCS = {"chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "chromium"}


def running_browsers() -> list[str]:
    try:
        import psutil
    except ImportError:
        return []
    found = set()
    for p in psutil.process_iter(["name"]):
        name = (p.info.get("name") or "").lower().removesuffix(".exe")
        if name in BROWSER_PROCS:
            found.add(name)
    return sorted(found)


# ── mentés törlés előtt ──────────────────────────────────────────────────────

def _prune_backups(keep: int) -> None:
    zips = sorted(backups_dir().glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in zips[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def create_backup(cats: list[Category], min_age_days: float = 0) -> str | None:
    prof = store.active_profile()
    if not prof.get("auto_backup"):
        return None
    max_bytes = int(prof.get("backup_max_mb", 200)) * 1024 * 1024
    path = backups_dir() / f"backup_{datetime.now():%Y%m%d_%H%M%S}.zip"
    added = 0
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for c in cats:
                for tg in _live_targets(c):
                    for fp, st in candidates(tg.path, **_rules(tg, min_age_days)):
                        if added + st.st_size > max_bytes:
                            continue
                        try:
                            zf.write(fp, os.path.join(c.id, os.path.relpath(fp, os.path.dirname(tg.path))))
                            added += st.st_size
                        except (OSError, ValueError):
                            pass
        if added == 0:
            path.unlink(missing_ok=True)
            return None
        _prune_backups(int(prof.get("backup_keep", 5)))
        return path.name
    except OSError:
        path.unlink(missing_ok=True)
        return None


# ── tisztítás ────────────────────────────────────────────────────────────────

def _clean_winupdate(c: Category):
    """A Windows Update szolgáltatást a törlés idejére leállítjuk, utána újraindítjuk."""
    winapi.run_hidden(["net", "stop", "wuauserv"], timeout=60)
    winapi.run_hidden(["net", "stop", "bits"], timeout=60)
    try:
        res = [clean_dir(t.path) for t in _live_targets(c)]
    finally:
        winapi.run_hidden(["net", "start", "bits"], timeout=60)
        winapi.run_hidden(["net", "start", "wuauserv"], timeout=60)
    winapi.powershell("Delete-DeliveryOptimizationCache -Force -ErrorAction SilentlyContinue", timeout=120)
    return [sum(x[i] for x in res) for i in range(3)] if res else [0, 0, 0]


def clean(cat_ids: list[str], min_age_days: float = 0, auto: bool = False) -> dict:
    started = time.time()
    admin = winapi.is_admin()
    chosen = [c for c in categories() if c.id in cat_ids]
    skipped = [c.label for c in chosen if c.admin and WIN and not admin]
    chosen = [c for c in chosen if not (c.admin and WIN and not admin)]

    backup = create_backup([c for c in chosen if c.id not in ("trash", "winupdate")], min_age_days)
    details = []
    tot_freed = tot_files = tot_err = 0
    for c in chosen:
        files = errs = freed = 0
        if c.id == "trash" and WIN:
            size, count = winapi.recycle_bin_info()
            if count and winapi.empty_recycle_bin():
                files, freed = count, size
        elif c.id == "winupdate" and WIN:
            files, errs, freed = _clean_winupdate(c)
        else:
            for tg in _live_targets(c):
                r, e, f = clean_dir(tg.path, **_rules(tg, min_age_days))
                files += r
                errs += e
                freed += f
        details.append({"id": c.id, "category": c.label, "files": files, "errors": errs,
                        "freed": fmt(freed), "freed_bytes": freed})
        tot_freed += freed
        tot_files += files
        tot_err += errs

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auto": auto,
        "categories": [c.id for c in chosen],
        "total_freed": fmt(tot_freed), "total_freed_bytes": tot_freed,
        "total_files": tot_files, "total_errors": tot_err,
        "duration_s": round(time.time() - started, 1),
        "details": details, "skipped_admin": skipped, "backup": backup,
    }
    store.add_history(entry)
    return entry
