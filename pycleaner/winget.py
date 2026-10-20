"""Programfrissítő a Windows beépített csomagkezelőjével (winget)."""

import re
import subprocess

from . import winapi
from .i18n import t
from .paths import SYSTEM

FLAGS = ["--accept-source-agreements", "--disable-interactivity"]


def parse_table(text: str) -> list[dict]:
    """A `winget upgrade` táblázata → sorok. Az oszlophatárokat a fejléc szavainak pozíciója adja
    (a szaggatott vonal feletti sor), így a fordított fejlécekkel és a szóközös verziókkal is működik."""
    lines = [ln.split("\r")[-1].rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    try:
        sep = next(i for i, ln in enumerate(lines) if re.fullmatch(r"-{20,}", ln.strip()))
    except StopIteration:
        return []
    header = lines[sep - 1] if sep else ""
    starts = [m.start() for m in re.finditer(r"\S+", header)]
    if len(starts) < 4:
        return []
    rows = []
    for ln in lines[sep + 1:]:
        if not ln.strip() or len(ln) <= starts[-1] or re.fullmatch(r"-{20,}", ln.strip()):
            break
        cells = [ln[a:b].strip() for a, b in zip(starts, starts[1:] + [None])]
        name, pid, cur, avail = cells[:4]
        source = cells[4] if len(cells) > 4 else ""
        if not pid or " " in pid:
            continue
        rows.append({"name": name, "id": pid, "version": cur, "available": avail, "source": source,
                     "truncated": pid.endswith("…") or name.endswith("…")})
    return rows


def available() -> bool:
    if SYSTEM != "Windows":
        return False
    r = winapi.powershell("if (Get-Command winget -ErrorAction SilentlyContinue) { 'OK' }", timeout=30)
    return "OK" in r.stdout


def list_upgrades() -> dict:
    if not available():
        return {"available": False, "packages": [],
                "error": t("A winget nem érhető el ezen a gépen (Microsoft Store → Alkalmazástelepítő).")}
    r = winapi.powershell("winget upgrade " + " ".join(FLAGS) + " 2>&1 | Out-String -Width 500", timeout=300)
    pkgs = [p for p in parse_table(r.stdout) if p["source"].lower() in ("winget", "msstore", "")]
    return {"available": True, "packages": pkgs}


def upgrade(job: dict, ids: list[str]) -> list[dict]:
    """Csomagok frissítése egyenként; a kimenet a munka naplójába kerül."""
    results = []
    for n, pid in enumerate(ids, 1):
        job["log"].append(f"[{n}/{len(ids)}] {pid}")
        args = ["winget", "upgrade", "--id", pid, "--exact", "--silent", "--accept-package-agreements", *FLAGS]
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace",
                                    creationflags=winapi.CREATE_NO_WINDOW if winapi.IS_WINDOWS else 0)
            for line in proc.stdout:
                line = line.split("\r")[-1].strip()
                # a winget forgó „- \ | /” jelei és a folyamatjelző sávok nem kellenek a naplóba
                if len(line) > 2 and not re.fullmatch(r"[\s\-\\|/█▒]+.*?(KB|MB|GB|%)?", line):
                    job["log"].append("   " + line[:200])
            rc = proc.wait(timeout=3600)
        except (OSError, subprocess.TimeoutExpired) as e:
            rc = -1
            job["log"].append("   " + str(e))
        ok = rc == 0
        results.append({"id": pid, "ok": ok, "code": rc})
        job["log"].append("   " + (t("kész") if ok else t("hiba (kód: {rc})", rc=rc)))
    return results
