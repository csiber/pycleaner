"""Lemezelemzés: felhasználói mappák mérete és nagy fájlok keresése."""

import heapq
import os
import tempfile
from pathlib import Path

from .fsutil import dir_size, fmt

SKIP = {"$Recycle.Bin", "System Volume Information", "Windows", "node_modules", "__pycache__", ".git"}


def user_folders() -> list[dict]:
    home = Path.home()
    names = [("Asztal", "Desktop"), ("Dokumentumok", "Documents"), ("Letöltések", "Downloads"),
             ("Képek", "Pictures"), ("Videók", "Videos"), ("Zene", "Music"),
             ("OneDrive", "OneDrive")]
    out = []
    for label, sub in names:
        p = home / sub
        if p.is_dir():
            size, count = dir_size(str(p))
            out.append({"name": label, "path": str(p), "size": size, "size_fmt": fmt(size), "files": count})
    tmp = tempfile.gettempdir()
    size, count = dir_size(tmp)
    out.append({"name": "Ideiglenes", "path": tmp, "size": size, "size_fmt": fmt(size), "files": count})
    out.sort(key=lambda x: x["size"], reverse=True)
    return out


def large_files(root: str, min_mb: float = 100, limit: int = 100) -> list[dict]:
    min_b = int(max(1, min_mb) * 1024 * 1024)
    heap: list[tuple[int, str]] = []
    for dp, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            fp = os.path.join(dp, f)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if st.st_size >= min_b and not os.path.islink(fp):
                item = (st.st_size, fp)
                if len(heap) < limit:
                    heapq.heappush(heap, item)
                else:
                    heapq.heappushpop(heap, item)
    return [{"name": os.path.basename(p), "path": p, "size": s, "size_fmt": fmt(s),
             "ext": os.path.splitext(p)[1].lower().lstrip(".")}
            for s, p in sorted(heap, reverse=True)]
