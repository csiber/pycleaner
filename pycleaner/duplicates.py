"""Azonos tartalmú fájlok keresése: méret → első 64 KB → teljes BLAKE2b-hash."""

import hashlib
import os
from collections import defaultdict

from .fsutil import fmt

SKIP_DIRS = {"node_modules", "__pycache__", "$Recycle.Bin", "System Volume Information", "Windows",
             "Program Files", "Program Files (x86)", "ProgramData", "AppData", ".git"}


def _walk(root: str, min_bytes: int, skip_hidden: bool = True):
    for dp, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (skip_hidden and d.startswith("."))]
        for f in files:
            fp = os.path.join(dp, f)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if st.st_size >= min_bytes and not os.path.islink(fp):
                yield fp, st


def _hash(fp: str, limit: int | None = None) -> str | None:
    h = hashlib.blake2b(digest_size=20)
    try:
        with open(fp, "rb") as f:
            remaining = limit
            while True:
                chunk = f.read(1 << 20 if remaining is None else min(1 << 20, remaining))
                if not chunk:
                    break
                h.update(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
                    if remaining <= 0:
                        break
    except OSError:
        return None
    return h.hexdigest()


def find(root: str, min_size_kb: int = 100, max_groups: int = 200) -> dict:
    by_size = defaultdict(list)
    scanned = 0
    for fp, st in _walk(root, max(1, min_size_kb) * 1024):
        by_size[st.st_size].append((fp, st.st_mtime))
        scanned += 1

    groups = []
    for size, items in by_size.items():
        if len(items) < 2:
            continue
        # gyors előszűrés az első 64 KB alapján, csak utána teljes hash
        by_head = defaultdict(list)
        for fp, mt in items:
            hh = _hash(fp, 65536)
            if hh:
                by_head[hh].append((fp, mt))
        for cand in by_head.values():
            if len(cand) < 2:
                continue
            by_full = defaultdict(list)
            for fp, mt in cand:
                hf = _hash(fp) if size > 65536 else _hash(fp, 65536)
                if hf:
                    by_full[hf].append((fp, mt))
            for digest, same in by_full.items():
                if len(same) < 2:
                    continue
                same.sort(key=lambda x: x[1], reverse=True)  # a legújabb elöl
                wasted = size * (len(same) - 1)
                groups.append({"hash": digest, "size": size, "size_fmt": fmt(size),
                               "wasted": wasted, "wasted_fmt": fmt(wasted),
                               "files": [{"path": p, "mtime": m} for p, m in same]})
    groups.sort(key=lambda g: g["wasted"], reverse=True)
    groups = groups[:max_groups]
    total = sum(g["wasted"] for g in groups)
    return {"groups": groups, "scanned": scanned, "total_wasted": total, "total_wasted_fmt": fmt(total)}
