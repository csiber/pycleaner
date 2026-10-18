"""Önálló HTML-riport az előzményekből (minden adat HTML-escape-elve)."""

import platform
from datetime import datetime
from html import escape

from . import __version__
from .fsutil import fmt

LABELS = {"temp": "Ideiglenes", "browser": "Böngésző", "thumbnails": "Bélyegképek", "crash": "Hibajelentések",
          "logs": "Naplók", "winupdate": "Windows Update", "shader": "Shader", "trash": "Lomtár",
          "custom": "Egyéni"}


def build(history: list) -> str:
    total = sum(e.get("total_freed_bytes", 0) for e in history)
    files = sum(e.get("total_files", 0) for e in history)
    rows = "".join(
        "<tr><td>{ts}</td><td>{cats}</td><td class=n>{freed}</td><td class=n>{files}</td><td>{kind}</td></tr>".format(
            ts=escape(str(e.get("timestamp", ""))),
            cats=escape(", ".join(LABELS.get(c, str(c)) for c in e.get("categories", []))),
            freed=escape(str(e.get("total_freed", ""))),
            files=int(e.get("total_files", 0) or 0),
            kind="Ütemezett" if e.get("auto") else "Kézi")
        for e in history[:200])
    now = datetime.now()
    return f"""<!doctype html>
<html lang="hu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PyCleaner riport — {now:%Y-%m-%d}</title>
<style>
:root{{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--tx:#1b1f24;--mut:#5b6573;--ln:#e3e6ea;--ac:#0b84b5}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111318;--card:#181b21;--tx:#e8eaed;--mut:#98a2b0;--ln:#262a33;--ac:#4cc3ee}}}}
body{{font:14px/1.5 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--tx);margin:0;padding:32px 16px}}
main{{max-width:960px;margin:0 auto}} h1{{font-size:26px;margin:0 0 4px}} .mut{{color:var(--mut)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:24px 0}}
.st{{background:var(--card);border:1px solid var(--ln);border-radius:10px;padding:16px}}
.st b{{display:block;font-size:24px;color:var(--ac);font-variant-numeric:tabular-nums}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--ln);border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--ln)}} th{{font-size:12px;color:var(--mut);font-weight:600}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}} footer{{margin-top:24px;font-size:12px}}
</style></head><body><main>
<h1>PyCleaner — tisztítási riport</h1>
<div class="mut">Készült: {now:%Y-%m-%d %H:%M} · {escape(platform.system())} {escape(platform.release())} · {escape(platform.node())}</div>
<div class="stats"><div class="st"><b>{len(history)}</b>tisztítás</div><div class="st"><b>{fmt(total)}</b>felszabadítva összesen</div><div class="st"><b>{files}</b>törölt fájl</div></div>
<table><thead><tr><th>Időpont</th><th>Kategóriák</th><th style="text-align:right">Felszabadítva</th><th style="text-align:right">Fájl</th><th>Mód</th></tr></thead>
<tbody>{rows or '<tr><td colspan=5 class=mut>Még nincs előzmény.</td></tr>'}</tbody></table>
<footer class="mut">PyCleaner {escape(__version__)} · github.com/csiber/pycleaner</footer>
</main></body></html>"""
