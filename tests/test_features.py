"""Az 5.1 funkciói: winget-feldolgozás, indítópult-jelző, gépállapot-szabályok, eltávolítás, nyelv."""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

from pycleaner import health, i18n, jobs, programs, store
from pycleaner.startup import approved_blob
from pycleaner.winget import parse_table

FIX = Path(__file__).parent / "fixtures"
WIN = sys.platform == "win32"
# A rendszert ténylegesen módosító tesztek (registry, Feladatütemező) csak kérésre futnak — a CI eldobható
# Windows-gépén be van kapcsolva, egy valódi, használt gépen alapból nem.
SYSTEM_TESTS = WIN and os.environ.get("PYC_SYSTEM_TESTS") == "1"


def test_winget_parse_real_layout():
    rows = parse_table((FIX / "winget_upgrade.txt").read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}
    assert len(rows) == 5
    assert by_id["AnyDesk.AnyDesk"]["version"] == "ad 9.7.0"          # szóköz a verzióban
    assert by_id["Python.Launcher"]["version"] == "< 3.14.7"
    assert by_id["Microsoft.WindowsTerminal"]["name"] == "Windows terminál"
    assert by_id["Vendor.LongNa…"]["truncated"] is True                # csonkolt azonosítót nem frissítünk


def test_winget_parse_localized_header():
    txt = ("Név              Azonosító   Verzió  Elérhető Forrás\n" + "-" * 56 + "\n"
           "Valami Program   Gyarto.App  1.0     1.1      winget\n2 frissítés érhető el.\n")
    assert parse_table(txt) == [{"name": "Valami Program", "id": "Gyarto.App", "version": "1.0", "available": "1.1",
                                 "source": "winget", "truncated": False}]


def test_winget_parse_garbage():
    assert parse_table("") == [] and parse_table("No installed package found.") == []


def test_startup_approved_blob():
    assert approved_blob(True) == b"\x02" + b"\x00" * 11
    off = approved_blob(False, now=1_700_000_000)
    assert len(off) == 12 and off[0] & 1 == 1                          # páratlan = letiltva (Feladatkezelő)


def test_health_rules():
    d = {"disks": [{"name": "SSD", "health": "Healthy", "wear": 92, "temp": 71, "size": 10 ** 12}],
         "defender": {"realtime": False}, "av": [],
         "hotfix": {"id": "KB1", "date": "2026-06-01T00:00:00"}, "pending_reboot": True,
         "battery": {"design": 50000, "full": 25000}, "startup": {"enabled": 20},
         "system": {"drives": [{"mount": "C:\\", "used_pct": 95, "free": 4 * 1024 ** 3, "free_fmt": "4 GB"}]}}
    f = health.evaluate(d, now=datetime(2026, 10, 20))
    levels = [x["level"] for x in f]
    assert levels == sorted(levels, key=["bad", "warn", "info", "ok"].index)   # súlyosság szerint rendezve
    titles = " | ".join(x["title"] for x in f if x["level"] == "bad")
    for part in ("kopás", "°C", "vírusvédelem", "frissítés", "Akkumulátor", "szinte tele"):
        assert part in titles, part


def test_health_free_space_absolute():
    big = {"system": {"drives": [{"mount": "C:\\", "used_pct": 82, "free": 166 * 1024 ** 3, "free_fmt": "166 GB"}]}}
    small = {"system": {"drives": [{"mount": "C:\\", "used_pct": 82, "free": 20 * 1024 ** 3, "free_fmt": "20 GB"}]}}
    assert health.evaluate(big)[0]["level"] == "ok"
    assert health.evaluate(small)[0]["level"] == "warn"


def test_health_report_escapes_and_brands():
    d = {"generated": "2026-10-20T10:00:00", "system": {"hostname": "<pc>", "os": "Windows 11"}, "score": 70,
         "findings": [{"level": "warn", "area": "X", "title": "<script>", "detail": "", "advice": ""}]}
    html = health.report_html(d, {"name": "PromNET Szerviz", "contact": "info@example.com", "note": "Köszönjük!"})
    assert "<script>" not in html and "&lt;script&gt;" in html and "PromNET Szerviz" in html and "Köszönjük!" in html


def test_uninstall_command_msi_uses_x():
    cmd = programs.uninstall_command({"uninstall": "MsiExec.exe /I{12345678-1234-1234-1234-123456789ABC}", "msi": True})
    assert cmd == ["msiexec.exe", "/x", "{12345678-1234-1234-1234-123456789ABC}"]


def test_leftovers_never_generic(tmp_path, monkeypatch):
    for v in ("APPDATA", "LOCALAPPDATA", "ProgramData", "ProgramFiles", "ProgramFiles(x86)"):
        monkeypatch.setenv(v, str(tmp_path / v))
        (tmp_path / v).mkdir()
    (tmp_path / "APPDATA" / "CoolEditor").mkdir()
    (tmp_path / "APPDATA" / "Microsoft").mkdir()
    (tmp_path / "LOCALAPPDATA" / "Acme" / "CoolEditor").mkdir(parents=True)
    found = {Path(x["path"]).relative_to(tmp_path).as_posix()
             for x in programs.leftovers({"name": "CoolEditor 2.4 (x64)", "publisher": "Acme", "location": ""})}
    assert found == {"APPDATA/CoolEditor", "LOCALAPPDATA/Acme/CoolEditor"}
    assert programs.leftovers({"name": "Microsoft", "publisher": "", "location": ""}) == []


def test_remove_leftovers_only_allowed(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("pycleaner.fsutil.send_to_trash", lambda p: calls.append(p))
    ok_dir = tmp_path / "ok"
    ok_dir.mkdir()
    res = programs.remove_leftovers([str(ok_dir), str(tmp_path / "other")], {os.path.normcase(os.path.abspath(ok_dir))})
    assert [r["ok"] for r in res] == [True, False] and calls == [str(ok_dir)]


def test_jobs_lifecycle():
    jid = jobs.start("teszt", "Teszt", lambda job, x: job["log"].append("fut") or x * 2, 21)
    for _ in range(100):
        j = jobs.get(jid)
        if j["status"] != "running":
            break
        import time
        time.sleep(0.02)
    assert j["status"] == "done" and j["result"] == 42 and j["log"] == ["fut"]
    bad = jobs.start("teszt", "Hiba", lambda job: 1 / 0)
    for _ in range(100):
        if jobs.get(bad)["status"] != "running":
            break
        import time
        time.sleep(0.02)
    assert jobs.get(bad)["status"] == "error"


def test_language_switch_and_fmt():
    from pycleaner.fsutil import fmt
    store.set_option("language", "en")
    assert i18n.t("Lomtár") == "Recycle Bin" and fmt(2048) == "2.0 KB"
    assert i18n.t("{n} fájl törölve", n=3) == "3 files deleted"
    store.set_option("language", "hu")
    assert i18n.t("Lomtár") == "Lomtár" and fmt(2048) == "2,0 KB"


def test_every_ui_string_is_translated():
    """Minden t()/tt() szöveg (JS és Python) és minden data-i18n felirat szerepel az angol táblában."""
    root = Path(__file__).resolve().parents[1] / "pycleaner"
    en = json.loads((root / "static" / "i18n-en.json").read_text(encoding="utf-8"))
    keys = set()
    js = re.sub(r"/\*.*?\*/", "", (root / "static" / "app.js").read_text(encoding="utf-8"), flags=re.S)
    for m in re.finditer(r"\btt?\(\s*(?:[^'()]*\?\s*)?'((?:[^'\\]|\\.)*)'(?:\s*:\s*'((?:[^'\\]|\\.)*)')?", js):
        keys.update(s for s in m.groups() if s)
    keys.update(s.strip() for s in re.findall(r"data-i18n>([^<]+)<", (root / "templates" / "index.html").read_text(encoding="utf-8")))
    for f in root.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        keys.update(re.findall(r'\bt\(\s*"((?:[^"\\]|\\.)*)"', src))
        keys.update(re.findall(r"\bt\(\s*'((?:[^'\\]|\\.)*)'", src))
    keys = {k for k in keys if re.search(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]", k)}
    same = {"Registry", "Program", "Skype", "Clipchamp", "Cortana", "Xbox Game Bar", "Mixed Reality Portal", "Microsoft To Do",
            "Candy Crush Saga", "Candy Crush Soda Saga", "Solitaire Collection", "Registry (Run)", "{name}: {c} °C"}
    missing = sorted(k for k in keys if k not in en and k not in same)
    assert not missing, missing


def test_schedule_use_task_flag():
    s = store.save_schedule({"enabled": True, "use_task": True})
    assert s["use_task"] is True


# ── valódi Windows-integráció (a CI Windows-gépén fut; eldobható környezet) ──

@pytest.mark.skipif(not SYSTEM_TESTS, reason="rendszermódosító teszt: PYC_SYSTEM_TESTS=1 kell hozzá")
def test_startup_toggle_roundtrip():
    import winreg

    from pycleaner import startup
    name = "PyCleanerTeszt"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, startup.RUN, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, r'"C:\Windows\System32\notepad.exe" /x')
    try:
        item = next(i for i in startup.list_items() if i["name"] == name)
        assert item["enabled"] and item["source"] == "run_user" and not item["missing"]
        assert startup.set_enabled(item, False)[0]
        assert not next(i for i in startup.list_items() if i["name"] == name)["enabled"]
        assert startup.set_enabled(item, True)[0]
        assert next(i for i in startup.list_items() if i["name"] == name)["enabled"]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup.RUN) as k:   # a bejegyzés maga megmaradt
            assert winreg.QueryValueEx(k, name)[0].startswith('"C:')
    finally:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup.RUN, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup.APPROVED + r"\Run", 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass


@pytest.mark.skipif(not SYSTEM_TESTS, reason="rendszermódosító teszt: PYC_SYSTEM_TESTS=1 kell hozzá")
def test_scheduled_task_roundtrip():
    from pycleaner import scheduler
    ok, msg = scheduler.register_task(6)
    try:
        assert ok, msg
        st = scheduler.task_status()
        assert st["exists"] and st["next"], st
    finally:
        scheduler.unregister_task()
    assert scheduler.task_status()["exists"] is False


@pytest.mark.skipif(not WIN, reason="Windows-only")
def test_programs_list_on_windows():
    progs = programs.list_programs()
    assert progs and all(p["name"] and p["uninstall"] for p in progs)


@pytest.mark.skipif(not WIN, reason="Windows-only")
def test_health_collect_on_windows():
    d = health.collect()
    assert 0 <= d["score"] <= 100 and d["findings"]
