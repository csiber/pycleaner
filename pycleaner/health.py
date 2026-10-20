"""Gépállapot-felmérés: lemezek egészsége, szabad hely, védelem, frissítések, akkumulátor,
indítópult — megállapítások súlyossággal és javaslattal, plusz nyomtatható HTML-riport."""

import json
import os
import tempfile
from datetime import datetime, timedelta

from . import winapi
from .fsutil import fmt
from .i18n import lang, t
from .paths import SYSTEM

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

_PS = r"""
$r = @{}
try { $r.disks = @(Get-PhysicalDisk | ForEach-Object {
  $c = $_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue
  @{ name = $_.FriendlyName; media = [string]$_.MediaType; bus = [string]$_.BusType; health = [string]$_.HealthStatus;
     size = $_.Size; temp = $c.Temperature; wear = $c.Wear; hours = $c.PowerOnHours } }) } catch {}
try { $m = Get-MpComputerStatus -ErrorAction Stop
  $r.defender = @{ enabled = $m.AntivirusEnabled; realtime = $m.RealTimeProtectionEnabled;
    sigdate = $m.AntivirusSignatureLastUpdated.ToString('o') } } catch {}
try { $r.av = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop |
  ForEach-Object { @{ name = $_.displayName; state = $_.productState } }) } catch {}
try { $h = Get-HotFix | Where-Object InstalledOn | Sort-Object InstalledOn -Descending | Select-Object -First 1
  if ($h) { $r.hotfix = @{ id = $h.HotFixID; date = $h.InstalledOn.ToString('o') } } } catch {}
try { if (Get-CimInstance Win32_Battery) {
  $f = Join-Path $env:TEMP 'pyc-battery.xml'
  powercfg /batteryreport /xml /output $f | Out-Null
  [xml]$x = Get-Content $f -Raw; Remove-Item $f -ErrorAction SilentlyContinue
  $b = $x.BatteryReport.Batteries.Battery | Select-Object -First 1
  $r.battery = @{ design = [int64]$b.DesignCapacity; full = [int64]$b.FullChargeCapacity; cycles = [int]$b.CycleCount } } } catch {}
$r | ConvertTo-Json -Depth 5 -Compress
"""


def _pending_reboot() -> bool:
    if SYSTEM != "Windows":
        return False
    import winreg
    keys = [r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"]
    for k in keys:
        try:
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, k).Close()
            return True
        except OSError:
            pass
    return False


def collect(job: dict | None = None) -> dict:
    def step(msg):
        if job is not None:
            job["log"].append(msg)

    from . import cleaner, monitor, startup
    data: dict = {"generated": datetime.now().isoformat(timespec="seconds"), "system": monitor.system_info()}
    if SYSTEM == "Windows":
        step(t("Lemezek, védelem és frissítések lekérdezése…"))
        r = winapi.powershell(_PS, timeout=180)
        try:
            data.update(json.loads(r.stdout.strip() or "{}"))
        except ValueError:
            pass
        data["pending_reboot"] = _pending_reboot()
        step(t("Indítópult átnézése…"))
        try:
            items = startup.list_items()
            data["startup"] = {"enabled": sum(1 for i in items if i["enabled"]), "total": len(items)}
        except Exception:  # noqa: BLE001
            pass
    step(t("Felszabadítható hely mérése…"))
    scan = cleaner.scan()
    meta = {c["id"]: c for c in cleaner.category_meta()}
    data["reclaimable"] = sum(v["size"] for k, v in scan.items() if meta.get(k, {}).get("default"))
    if psutil:
        data["uptime_days"] = round((datetime.now().timestamp() - psutil.boot_time()) / 86400, 1)
        data["ram"] = {"total": psutil.virtual_memory().total, "pct": psutil.virtual_memory().percent}
    step(t("Értékelés…"))
    data["findings"] = evaluate(data)
    bad = sum(1 for f in data["findings"] if f["level"] == "bad")
    warn = sum(1 for f in data["findings"] if f["level"] == "warn")
    data["score"] = max(0, min(100, 100 - 15 * bad - 5 * warn))
    return data


def _f(level, area, title, detail="", advice=""):
    return {"level": level, "area": area, "title": title, "detail": detail, "advice": advice}


def evaluate(d: dict, now: datetime | None = None) -> list[dict]:
    """Megállapítások szabályok alapján. level: ok / warn / bad / info."""
    now = now or datetime.now()
    out: list[dict] = []
    # lemezek
    for disk in d.get("disks") or []:
        name = disk.get("name") or t("Lemez")
        health = (disk.get("health") or "").lower()
        if health and health != "healthy":
            out.append(_f("bad", t("Lemez"), t("{name}: a lemez állapota „{h}”", name=name, h=disk.get("health")),
                          advice=t("Azonnal készíts biztonsági mentést, és cseréltesd a lemezt.")))
        wear = disk.get("wear")
        if isinstance(wear, (int, float)) and wear >= 80:
            out.append(_f("bad" if wear >= 90 else "warn", t("Lemez"), t("{name}: {w}%-os kopás", name=name, w=wear),
                          advice=t("Az SSD élettartama a végéhez közeledik — tervezd be a cseréjét.")))
        temp = disk.get("temp")
        if isinstance(temp, (int, float)) and temp >= 60:
            out.append(_f("bad" if temp >= 70 else "warn", t("Lemez"), t("{name}: {c} °C", name=name, c=temp),
                          advice=t("Magas lemezhőmérséklet — ellenőrizd a szellőzést és a hűtést.")))
        if health == "healthy" and not (isinstance(wear, (int, float)) and wear >= 80):
            detail = ", ".join(x for x in [disk.get("media"), fmt(disk.get("size") or 0),
                                           f"{temp} °C" if isinstance(temp, (int, float)) and temp else "",
                                           t("{w}% kopás", w=wear) if isinstance(wear, (int, float)) else ""] if x)
            out.append(_f("ok", t("Lemez"), t("{name}: egészséges", name=name), detail))
    # szabad hely
    for drv in (d.get("system") or {}).get("drives") or []:
        free_pct = 100 - drv.get("used_pct", 0)
        free = drv.get("free") or 0
        label = drv.get("mount", "")
        gb = 1024 ** 3
        # nagy lemezen a százalék önmagában félrevezető (930 GB-ból 160 GB szabad bőven elég)
        if free < 5 * gb or (free_pct < 10 and free < 20 * gb):
            out.append(_f("bad", t("Tárhely"), t("{d} szinte tele: {f} szabad", d=label, f=drv.get("free_fmt")),
                          advice=t("Futtass tisztítást, és nézd át a nagy fájlokat a Lemezelemzőben.")))
        elif free_pct < 20 and free < 50 * gb:
            out.append(_f("warn", t("Tárhely"), t("{d}: kevés a szabad hely ({f})", d=label, f=drv.get("free_fmt")),
                          advice=t("Futtass tisztítást, és nézd át a nagy fájlokat a Lemezelemzőben.")))
        else:
            out.append(_f("ok", t("Tárhely"), t("{d}: {f} szabad", d=label, f=drv.get("free_fmt"))))
    rec = d.get("reclaimable") or 0
    if rec >= 5 * 1024 ** 3:
        out.append(_f("warn", t("Tárhely"), t("{s} felszabadítható felesleges fájl", s=fmt(rec)),
                      advice=t("Futtass egy gyors tisztítást.")))
    # védelem
    if SYSTEM == "Windows" or d.get("defender") or d.get("av"):
        dfd = d.get("defender") or {}
        others = [a.get("name") for a in d.get("av") or [] if a.get("name") and "defender" not in a.get("name", "").lower()]
        if dfd.get("realtime"):
            sig = dfd.get("sigdate")
            try:
                age = (now - datetime.fromisoformat(sig[:19])).days if sig else None
            except ValueError:
                age = None
            if age is not None and age > 7:
                out.append(_f("warn", t("Védelem"), t("A víruskereső adatbázisa {n} napos", n=age),
                              advice=t("Futtasd a Windows Update-et.")))
            else:
                out.append(_f("ok", t("Védelem"), t("Microsoft Defender: valós idejű védelem bekapcsolva")))
        elif others:
            out.append(_f("ok", t("Védelem"), t("Víruskereső: {n}", n=", ".join(others))))
        elif d.get("defender") is not None:
            out.append(_f("bad", t("Védelem"), t("Nincs bekapcsolt valós idejű vírusvédelem"),
                          advice=t("Kapcsold be a Windows Biztonság → Vírus- és fenyegetésvédelem pontban.")))
    # frissítések
    hf = d.get("hotfix") or {}
    if hf.get("date"):
        try:
            days = (now - datetime.fromisoformat(hf["date"][:19])).days
            if days > 90:
                out.append(_f("bad", t("Frissítések"), t("Az utolsó Windows-frissítés {n} napja volt", n=days),
                              advice=t("Futtasd a Windows Update-et — a gép valószínűleg nem kap biztonsági javításokat.")))
            elif days > 45:
                out.append(_f("warn", t("Frissítések"), t("Az utolsó Windows-frissítés {n} napja volt", n=days),
                              advice=t("Futtasd a Windows Update-et.")))
            else:
                out.append(_f("ok", t("Frissítések"), t("Windows-frissítések naprakészek ({id}, {n} napja)", id=hf.get("id"), n=days)))
        except ValueError:
            pass
    if d.get("pending_reboot"):
        out.append(_f("warn", t("Frissítések"), t("Újraindításra váró frissítés"),
                      advice=t("Indítsd újra a gépet, hogy a frissítések érvénybe lépjenek.")))
    if d.get("winget_updates"):
        out.append(_f("warn", t("Frissítések"), t("{n} programhoz érhető el frissítés", n=d["winget_updates"]),
                      advice=t("A Programfrissítő oldalon egy kattintással frissíthetők.")))
    up = d.get("uptime_days")
    if isinstance(up, (int, float)) and up > 14:
        out.append(_f("warn", t("Rendszer"), t("{n} napja nem volt újraindítva", n=int(up)),
                      advice=t("Egy újraindítás felszabadítja a memóriát, és befejezi a frissítéseket.")))
    # akkumulátor
    bat = d.get("battery") or {}
    if bat.get("design") and bat.get("full"):
        h = round(bat["full"] / bat["design"] * 100)
        lvl = "bad" if h < 60 else "warn" if h < 80 else "ok"
        out.append(_f(lvl, t("Akkumulátor"), t("Akkumulátor-kapacitás: {p}% az eredetihez képest", p=h),
                      t("{c} töltési ciklus", c=bat.get("cycles")) if bat.get("cycles") else "",
                      t("Az akkumulátor elhasználódott — cseréje javasolt.") if lvl != "ok" else ""))
    # indítópult, memória
    st = d.get("startup") or {}
    if st.get("enabled", 0) > 15:
        out.append(_f("warn", t("Rendszer"), t("{n} program indul a bejelentkezéskor", n=st["enabled"]),
                      advice=t("Kapcsold ki a feleslegeseket az Indítópult oldalon — ez gyorsítja a legjobban az indulást.")))
    elif st:
        out.append(_f("ok", t("Rendszer"), t("{n} program indul a bejelentkezéskor", n=st.get("enabled", 0))))
    ram = d.get("ram") or {}
    if ram.get("total") and ram["total"] < 7.5 * 1024 ** 3:
        out.append(_f("info", t("Rendszer"), t("{r} memória", r=fmt(ram["total"])),
                      advice=t("Windows 11-hez legalább 8 GB ajánlott; bővítéssel érezhetően gyorsulna a gép.")))
    order = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    out.sort(key=lambda f: order[f["level"]])
    return out


def report_html(d: dict, service: dict | None = None) -> str:
    from html import escape as e

    from . import __version__
    service = service or {}
    sysi = d.get("system") or {}
    colors = {"ok": "#128a52", "warn": "#a8650a", "bad": "#c9303a", "info": "#2563a8"}
    labels = {"ok": t("Rendben"), "warn": t("Figyelem"), "bad": t("Sürgős"), "info": t("Tudnivaló")}
    rows = "".join(
        f'<tr><td><span class="lvl" style="background:{colors[f["level"]]}">{e(labels[f["level"]])}</span></td>'
        f'<td><b>{e(f["title"])}</b>{"<div class=d>" + e(f["detail"]) + "</div>" if f["detail"] else ""}'
        f'{"<div class=a>→ " + e(f["advice"]) + "</div>" if f["advice"] else ""}</td><td class=ar>{e(f["area"])}</td></tr>'
        for f in d.get("findings", []))
    score = d.get("score", 0)
    sc = "#128a52" if score >= 85 else "#a8650a" if score >= 60 else "#c9303a"
    head = ""
    if service.get("name") or service.get("contact"):
        head = (f'<div class="svc"><b>{e(service.get("name", ""))}</b><span>{e(service.get("contact", ""))}</span></div>')
    note = f'<div class="note">{e(service.get("note", "")).replace(chr(10), "<br>")}</div>' if service.get("note") else ""
    when = datetime.fromisoformat(d["generated"]).strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="{lang()}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(t('Gépállapot-jelentés'))} — {e(sysi.get('hostname', ''))}</title>
<style>
body{{font:14px/1.5 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;color:#16191d;background:#f3f4f6;margin:0;padding:28px 16px}}
main{{max-width:860px;margin:0 auto;background:#fff;border:1px solid #e1e4e8;border-radius:12px;padding:28px 32px}}
.top{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;border-bottom:1px solid #e1e4e8;padding-bottom:16px}}
h1{{font-size:24px;margin:0}} .sub{{color:#4d5762;font-size:13px}} .svc{{text-align:right}} .svc b{{display:block;font-size:16px}} .svc span{{color:#4d5762;font-size:13px;white-space:pre-line}}
.score{{display:flex;align-items:center;gap:18px;margin:18px 0}} .ring{{width:76px;height:76px;border-radius:50%;display:grid;place-items:center;font-size:24px;font-weight:700;color:{sc};border:7px solid {sc}}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;margin:0;font-size:13px}} dt{{color:#4d5762}} dd{{margin:0}}
table{{width:100%;border-collapse:collapse;margin-top:14px}} td{{padding:10px 8px;border-top:1px solid #e1e4e8;vertical-align:top}}
.lvl{{display:inline-block;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap}}
.d{{color:#4d5762;font-size:12.5px}} .a{{color:#16191d;font-size:13px;margin-top:2px}} .ar{{color:#7f8995;font-size:12px;text-align:right;white-space:nowrap}}
.note{{margin-top:18px;padding:12px 14px;background:#f7f8fa;border-radius:8px;font-size:13px}}
footer{{margin-top:18px;color:#7f8995;font-size:11.5px;display:flex;justify-content:space-between}}
.print{{position:fixed;right:20px;top:20px;padding:9px 16px;border-radius:8px;border:0;background:#1170a8;color:#fff;font:600 14px inherit;cursor:pointer}}
@media print{{body{{background:#fff;padding:0}} main{{border:0;padding:0}} .print{{display:none}}}}
</style></head><body><button class="print" onclick="print()">{e(t('Nyomtatás / PDF'))}</button><main>
<div class="top"><div><h1>{e(t('Gépállapot-jelentés'))}</h1><div class="sub">{e(sysi.get('hostname', ''))} · {e(sysi.get('os', ''))} · {e(when)}</div></div>{head}</div>
<div class="score"><div class="ring">{score}</div><dl>
<dt>{e(t('Processzor'))}</dt><dd>{e(sysi.get('processor', ''))}</dd>
<dt>{e(t('Memória'))}</dt><dd>{e(sysi.get('ram_total', ''))}</dd>
<dt>{e(t('Utolsó indítás'))}</dt><dd>{e(sysi.get('boot_time', ''))}</dd></dl></div>
<table>{rows}</table>{note}
<footer><span>PyCleaner {e(__version__)} · github.com/csiber/pycleaner</span><span>{e(t('A jelentés a készítés pillanatát tükrözi.'))}</span></footer>
</main></body></html>"""


def save_report(d: dict, service: dict | None = None) -> str:
    from .paths import data_dir
    folder = data_dir() / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    host = "".join(ch for ch in (d.get("system") or {}).get("hostname", "pc") if ch.isalnum() or ch in "-_")[:30]
    p = folder / f"gepallapot_{host}_{datetime.now():%Y%m%d_%H%M}.html"
    p.write_text(report_html(d, service), encoding="utf-8")
    return str(p)
