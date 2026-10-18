"""Fájlrendszer-segédek: méretezés, biztonságos törlés (szimbolikus linket soha nem követ)."""

import os
import shutil
import stat
import time
from pathlib import Path
from typing import Iterable


def fmt(n: float) -> str:
    n = float(n or 0)
    if n < 1024:
        return f"{int(n)} B"
    for unit in ("KB", "MB"):
        n /= 1024
        if n < 1024:
            return f"{n:.1f} {unit}".replace(".", ",")
    return f"{n / 1024:.2f} GB".replace(".", ",")


def _walk_files(path: str):
    """Fájlok bejárása szimbolikus linkek követése nélkül. (dirpath, név, lstat) hármasokat ad."""
    for dp, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            fp = os.path.join(dp, name)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                yield fp, st


def dir_size(path: str):
    """(bájt, fájlszám) egy teljes mappára, linkek követése nélkül."""
    total = count = 0
    for _fp, st in _walk_files(path):
        total += st.st_size
        count += 1
    return total, count


def _remove_file(fp: str) -> None:
    try:
        os.chmod(fp, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    os.remove(fp)


def candidates(path: str, min_age_days: float = 0, suffixes: Iterable[str] | None = None,
               skip_hidden_top: bool = False, prefix: tuple[str, ...] | None = None):
    """A törlendő fájlok (útvonal, lstat) párjai egy mappán belül. A mappa maga nem jelölt.

    - szimbolikus linket / junctiont nem követ (és magát a linket sem adja vissza),
    - csak szabályos fájlokat ad (socketet, FIFO-t nem),
    - min_age_days: ennél frissebb fájlok kimaradnak,
    - suffixes / prefix: fájlnév-szűrők (kisbetűsítve),
    - skip_hidden_top: a legfelső szinten a pontos nevű bejegyzések kimaradnak (POSIX /tmp).
    """
    if not os.path.isdir(path) or os.path.islink(path) or _is_junction(path):
        return
    now = time.time()
    sfx = tuple(s.lower() for s in suffixes) if suffixes else None
    try:
        top = os.listdir(path)
    except OSError:
        return
    for entry in top:
        if skip_hidden_top and entry.startswith("."):
            continue
        ep = os.path.join(path, entry)
        try:
            st = os.lstat(ep)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode) or _is_junction(ep):
            continue
        if stat.S_ISREG(st.st_mode):
            items = [(ep, st)]
        elif stat.S_ISDIR(st.st_mode):
            items = _walk_files(ep)
        else:
            continue
        for fp, fst in items:
            name = os.path.basename(fp).lower()
            if sfx and not name.endswith(sfx):
                continue
            if prefix and not name.startswith(prefix):
                continue
            if min_age_days > 0 and (now - fst.st_mtime) / 86400 < min_age_days:
                continue
            yield fp, fst


def measure(path: str, **rules):
    """(bájt, fájlszám) — pontosan annyi, amennyit a clean_dir azonos szabályokkal törölne."""
    total = count = 0
    for _fp, st in candidates(path, **rules):
        total += st.st_size
        count += 1
    return total, count


def clean_dir(path: str, min_age_days: float = 0, suffixes: Iterable[str] | None = None,
              skip_hidden_top: bool = False, prefix: tuple[str, ...] | None = None):
    """Egy mappa tartalmának törlése a candidates() szabályai szerint; a mappa maga megmarad,
    az üressé vált almappák eltűnnek. Visszatér: (törölt fájlok, hibák, felszabadított bájt)."""
    removed = errors = freed = 0
    if not os.path.isdir(path):
        return 0, 0, 0
    for fp, st in candidates(path, min_age_days, suffixes, skip_hidden_top, prefix):
        try:
            _remove_file(fp)
            removed += 1
            freed += st.st_size
        except OSError:
            errors += 1
    try:
        for entry in os.listdir(path):
            if skip_hidden_top and entry.startswith("."):
                continue
            ep = os.path.join(path, entry)
            if os.path.isdir(ep) and not os.path.islink(ep) and not _is_junction(ep):
                _prune_empty_dirs(ep)
    except OSError:
        pass
    return removed, errors, freed


def _prune_empty_dirs(path: str) -> None:
    for dp, _dirs, _files in os.walk(path, topdown=False, followlinks=False):
        if os.path.islink(dp) or _is_junction(dp):
            continue
        try:
            os.rmdir(dp)
        except OSError:
            pass


def _is_junction(path: str) -> bool:
    fn = getattr(os.path, "isjunction", None)  # Python 3.12+
    try:
        return bool(fn and fn(path))
    except OSError:
        return False


def send_to_trash(path: str) -> None:
    """Lomtárba helyezés (ha a send2trash elérhető), különben végleges törlés."""
    try:
        from send2trash import send2trash
    except ImportError:  # pragma: no cover - a requirements tartalmazza
        _remove_file(path)
        return
    send2trash(path)


def disk_usage(path: str):
    try:
        u = shutil.disk_usage(path)
        return {"total": u.total, "used": u.used, "free": u.free,
                "total_fmt": fmt(u.total), "used_fmt": fmt(u.used), "free_fmt": fmt(u.free),
                "used_pct": round(u.used / u.total * 100, 1) if u.total else 0}
    except OSError:
        return {}


def file_stat(path: str):
    try:
        st = os.lstat(path)
        return st if stat.S_ISREG(st.st_mode) else None
    except OSError:
        return None


def expand(p: str) -> str:
    return os.path.normpath(os.path.expandvars(os.path.expanduser(p)))


def existing(paths: Iterable[str]) -> list[str]:
    seen, out = set(), []
    for p in paths:
        if not p or "%" in p or "$" in p:
            continue  # nem feloldott környezeti változó
        key = os.path.normcase(os.path.abspath(p))
        if key in seen or not os.path.isdir(p):
            continue
        seen.add(key)
        out.append(p)
    return out


def glob_dirs(pattern_root: str, *parts: str) -> list[str]:
    """Minden profilmappa alatti ugyanolyan relatív útvonal (pl. Chrome 'Default', 'Profile 1')."""
    root = Path(pattern_root)
    if not root.is_dir():
        return []
    out = []
    try:
        for child in root.iterdir():
            if child.is_dir() and not child.is_symlink():
                cand = child.joinpath(*parts)
                if cand.is_dir():
                    out.append(str(cand))
    except OSError:
        pass
    return out
