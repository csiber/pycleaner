"""Frissítés-ellenőrzés a GitHub Releases alapján (csak a verziószámot kérdezi le)."""

import json
import re
import urllib.request

from . import REPO, __version__

API = f"https://api.github.com/repos/{REPO}/releases/latest"


def _parse(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def check(timeout: float = 6) -> dict:
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"PyCleaner/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception as e:  # hálózati hiba, rate limit, nincs kiadás
        return {"ok": False, "current": __version__, "error": str(e)[:200]}
    latest = (data.get("tag_name") or "").lstrip("v")
    assets = [{"name": a.get("name"), "url": a.get("browser_download_url"), "size": a.get("size")}
              for a in data.get("assets", [])]
    return {"ok": True, "current": __version__, "latest": latest,
            "newer": _parse(latest) > _parse(__version__),
            "url": data.get("html_url"), "notes": (data.get("body") or "")[:4000], "assets": assets}
