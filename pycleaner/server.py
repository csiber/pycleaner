"""Flask-alkalmazás: a felület és a helyi API.

Biztonság: a szerver csak 127.0.0.1-en figyel; minden /api hívás a futásonként generált
tokent várja (X-PyCleaner-Token fejléc, SSE/letöltésnél ?t=), a Host fejlécnek
localhost-nak kell lennie (DNS-rebinding ellen), és fájlt csak olyan útvonalon lehet
törölni, amit a szerver előzőleg maga ajánlott fel (nagy fájlok / duplikátumok).
"""

import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory

from . import (__version__, analyzer, cleaner, duplicates, health, i18n, jobs, monitor, programs, registry, report,
               scheduler, startup, store, tweaks, updates, winapi, winget)
from .paths import backups_dir, data_dir, registry_backups_dir, resource_dir
from .i18n import t

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def _register_mimetypes() -> None:
    """Windowson a mimetypes a registryből olvas, ami gépenként hibás lehet; a nosniff miatt a rossz típus
    a felület elemeit (ikon, stílus, szkript) csendben eldobatná. Ezért rögzítjük a sajátjainkat."""
    import mimetypes
    for ext, typ in ((".svg", "image/svg+xml"), (".js", "text/javascript"), (".css", "text/css"),
                     (".json", "application/json"), (".png", "image/png"), (".ico", "image/x-icon")):
        mimetypes.add_type(typ, ext)


def create_app(token: str | None = None, *, hooks: dict | None = None) -> Flask:
    _register_mimetypes()
    res = resource_dir()
    # az ikonkészlet a HTML-be ágyazva megy ki (külső <use href="fájl.svg#…"> hivatkozás nélkül)
    try:
        icons_svg = (res / "static" / "icons.svg").read_text(encoding="utf-8")
    except OSError:
        icons_svg = ""
    app = Flask("pycleaner", template_folder=str(res / "templates"), static_folder=str(res / "static"))
    app.config["TOKEN"] = token or secrets.token_urlsafe(32)
    app.config["JSON_SORT_KEYS"] = False
    app.json.ensure_ascii = False
    hooks = hooks or {}
    offered: set[str] = set()          # törölhető útvonalak (amiket mi listáztunk)
    offered_lock = threading.Lock()
    reg_cache: dict[int, dict] = {}
    startup_cache: dict[int, dict] = {}
    program_cache: dict[int, dict] = {}
    winget_cache: dict = {"ids": set(), "count": None}
    leftover_ok: set[str] = set()
    last_health: dict = {}

    def offer(paths):
        with offered_lock:
            offered.update(os.path.normcase(os.path.abspath(p)) for p in paths)

    def is_offered(p: str) -> bool:
        with offered_lock:
            return os.path.normcase(os.path.abspath(p)) in offered

    def body() -> dict:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    # ── védelem ──────────────────────────────────────────────────────────────
    @app.before_request
    def guard():
        if _hostname(request.host or "") not in ALLOWED_HOSTS:
            abort(403)
        if request.path.startswith("/api/"):
            supplied = request.headers.get("X-PyCleaner-Token") or request.args.get("t", "")
            if not hmac.compare_digest(supplied, app.config["TOKEN"]):
                abort(403)

    @app.after_request
    def headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ── felület ──────────────────────────────────────────────────────────────
    @app.get("/")
    def index():
        from markupsafe import Markup
        return render_template("index.html", token=app.config["TOKEN"], version=__version__,
                               native=bool(hooks.get("native")), icons=Markup(icons_svg))

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder, "favicon.ico")

    # ── alapadatok ───────────────────────────────────────────────────────────
    @app.get("/api/bootstrap")
    def bootstrap():
        return jsonify({"version": __version__, "lang": i18n.lang(), "system": monitor.system_info(),
                        "categories": cleaner.category_meta(), "config": store.public_config(),
                        "schedule": store.load_schedule(), "native": bool(hooks.get("native")),
                        "can_pick_folder": bool(hooks.get("pick_folder")), "home": os.path.expanduser("~"),
                        "data_dir": str(data_dir())})

    @app.get("/api/sysinfo")
    def sysinfo():
        return jsonify(monitor.system_info())

    # ── tisztítás ────────────────────────────────────────────────────────────
    @app.post("/api/scan")
    def scan():
        return jsonify({"results": cleaner.scan(), "browsers": cleaner.running_browsers(),
                        "categories": cleaner.category_meta()})

    @app.post("/api/clean")
    def clean():
        b = body()
        cats = [c for c in b.get("categories", []) if c in cleaner.CATEGORY_IDS]
        try:
            min_age = max(0.0, min(3650.0, float(b.get("min_age_days", 0))))
        except (TypeError, ValueError):
            min_age = 0.0
        return jsonify(cleaner.clean(cats, min_age))

    # ── monitor (SSE) ────────────────────────────────────────────────────────
    @app.get("/api/monitor")
    def monitor_stream():
        def gen():
            s = monitor.Sampler()
            time.sleep(0.5)
            while True:
                try:
                    yield f"data: {json.dumps(s.sample(), ensure_ascii=False)}\n\n"
                except GeneratorExit:
                    return
                except Exception as e:  # noqa: BLE001 — a stream ne haljon meg egy hibás mintán
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(1.5)
        return Response(gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── elemzés ──────────────────────────────────────────────────────────────
    @app.get("/api/folders")
    def folders():
        return jsonify(analyzer.user_folders())

    def _root(b) -> str | None:
        p = os.path.expandvars(os.path.expanduser(str(b.get("path") or "~")))
        return p if os.path.isdir(p) else None

    @app.post("/api/large_files")
    def large_files():
        b = body()
        root = _root(b)
        if not root:
            return jsonify({"error": t("A mappa nem létezik.")}), 400
        items = analyzer.large_files(root, float(b.get("min_mb", 100) or 100))
        offer(i["path"] for i in items)
        return jsonify({"root": root, "files": items})

    @app.post("/api/duplicates")
    def find_duplicates():
        b = body()
        root = _root(b)
        if not root:
            return jsonify({"error": t("A mappa nem létezik.")}), 400
        r = duplicates.find(root, int(b.get("min_kb", 100) or 100))
        offer(f["path"] for g in r["groups"] for f in g["files"])
        r["root"] = root
        return jsonify(r)

    @app.post("/api/files/delete")
    def delete_files():
        from .fsutil import send_to_trash
        b = body()
        out = []
        for p in b.get("paths", [])[:500]:
            p = str(p)
            if not is_offered(p):
                out.append({"path": p, "ok": False, "error": t("Ezt a fájlt nem a PyCleaner listázta.")})
                continue
            try:
                if not os.path.isfile(p) or os.path.islink(p):
                    raise FileNotFoundError(t("A fájl már nem létezik."))
                send_to_trash(p)
                out.append({"path": p, "ok": True})
            except Exception as e:  # noqa: BLE001
                out.append({"path": p, "ok": False, "error": str(e)})
        return jsonify({"results": out})

    @app.post("/api/files/reveal")
    def reveal():
        p = str(body().get("path", ""))
        if not (is_offered(p) or os.path.isdir(p)):
            abort(400)
        return jsonify({"ok": winapi.reveal(p)})

    @app.post("/api/pick_folder")
    def pick_folder():
        fn = hooks.get("pick_folder")
        return jsonify({"path": fn() if fn else None})

    # ── registry ─────────────────────────────────────────────────────────────
    @app.get("/api/registry/scan")
    def reg_scan():
        issues = registry.scan()
        reg_cache.clear()
        reg_cache.update({i["id"]: i for i in issues})
        return jsonify({"issues": issues, "supported": winapi.IS_WINDOWS, "is_admin": winapi.is_admin()})

    @app.post("/api/registry/fix")
    def reg_fix():
        out = []
        for i in body().get("ids", []):
            issue = reg_cache.get(int(i)) if str(i).isdigit() else None
            if not issue:
                out.append({"id": i, "ok": False, "msg": t("Ismeretlen elem — futtasd újra a keresést.")})
                continue
            ok, msg = registry.fix(issue)
            out.append({"id": i, "ok": ok, "msg": msg})
        return jsonify({"results": out})

    @app.get("/api/registry/backups")
    def reg_backups():
        return jsonify({"backups": registry.list_backups(), "dir": str(registry_backups_dir())})

    @app.post("/api/registry/backups/open")
    def reg_backups_open():
        return jsonify({"ok": winapi.reveal(str(registry_backups_dir()))})

    # ── ütemező ──────────────────────────────────────────────────────────────
    @app.get("/api/schedule")
    def get_schedule():
        return jsonify(store.load_schedule())

    @app.post("/api/schedule")
    def set_schedule():
        b = body()
        b.pop("last_run", None)
        prev = store.load_schedule()
        s = store.save_schedule(b)
        if s["enabled"]:
            scheduler.start()
        task = {"ok": True, "msg": ""}
        relevant = ("enabled", "use_task", "interval_hours")
        if winapi.IS_WINDOWS and (s["use_task"] or prev["use_task"]) and any(prev[k] != s[k] for k in relevant):
            if s["enabled"] and s["use_task"]:
                ok, msg = scheduler.register_task(s["interval_hours"])
            else:
                ok, msg = scheduler.unregister_task()
            task = {"ok": ok, "msg": msg}
        return jsonify(dict(s, task=task))

    # ── beállítások / profilok ───────────────────────────────────────────────
    @app.get("/api/config")
    def get_config():
        return jsonify(store.public_config())

    @app.post("/api/config/profile")
    def update_profile():
        cfg = store.load_config()
        store.update_profile(cfg["active_profile"], body())
        return jsonify(store.public_config())

    @app.post("/api/config/profile/new")
    def new_profile():
        name = str(body().get("name", "")).strip()
        if not name:
            return jsonify({"error": t("Adj nevet a profilnak.")}), 400
        store.create_profile(name)
        return jsonify(store.public_config())

    @app.post("/api/config/profile/delete")
    def delete_profile():
        ok = store.delete_profile(str(body().get("id", "")))
        return jsonify({"ok": ok, "config": store.public_config()})

    @app.post("/api/config/profile/switch")
    def switch_profile():
        b = body()
        ok = store.switch_profile(str(b.get("id", "")), str(b.get("password", "")))
        return jsonify({"ok": ok, "config": store.public_config()})

    @app.post("/api/config/option")
    def set_option():
        b = body()
        store.set_option(str(b.get("key", "")), b.get("value"))
        return jsonify(store.public_config())

    @app.post("/api/config/validate_dir")
    def validate_dir():
        p = os.path.expandvars(os.path.expanduser(str(body().get("path", "")).strip()))
        if not p or not os.path.isdir(p):
            return jsonify({"ok": False, "msg": t("A mappa nem létezik.")})
        if cleaner.is_protected(p):
            return jsonify({"ok": False, "msg": t("Ez rendszer- vagy személyes mappa, ezt nem engedem üríteni.")})
        return jsonify({"ok": True, "path": os.path.normpath(p)})

    # ── előzmények / export ──────────────────────────────────────────────────
    @app.get("/api/history")
    def history():
        return jsonify(store.load_history())

    @app.post("/api/history/clear")
    def clear_history():
        store.clear_history()
        return jsonify({"ok": True})

    def _download(content: str, mime: str, name: str):
        return Response(content, mimetype=mime, headers={"Content-Disposition": f"attachment; filename={name}"})

    @app.get("/api/export/html")
    def export_html():
        return _download(report.build(store.load_history()), "text/html",
                         f"pycleaner_riport_{datetime.now():%Y%m%d}.html")

    @app.get("/api/export/json")
    def export_json():
        data = json.dumps({"exported": store.now_iso(), "version": __version__, "history": store.load_history()},
                          ensure_ascii=False, indent=2)
        return _download(data, "application/json", f"pycleaner_adatok_{datetime.now():%Y%m%d}.json")

    # ── mentések ─────────────────────────────────────────────────────────────
    _BK = re.compile(r"^backup_\d{8}_\d{6}\.zip$")

    @app.get("/api/backups")
    def backups():
        out = []
        for p in sorted(backups_dir().glob("backup_*.zip"), reverse=True):
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size,
                        "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
        return jsonify({"backups": out, "dir": str(backups_dir())})

    @app.get("/api/backups/file/<name>")
    def backup_file(name):
        if not _BK.match(name):
            abort(404)
        return send_from_directory(backups_dir(), name, as_attachment=True)

    @app.post("/api/backups/delete")
    def backup_delete():
        name = str(body().get("name", ""))
        if not _BK.match(name):
            return jsonify({"ok": False}), 400
        try:
            (backups_dir() / name).unlink()
            return jsonify({"ok": True})
        except OSError as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.post("/api/backups/open")
    def backups_open():
        return jsonify({"ok": winapi.reveal(str(backups_dir()))})

    # ── Windows-finomhangolás ────────────────────────────────────────────────
    @app.get("/api/tweaks/apps")
    def tweak_apps():
        return jsonify({"apps": tweaks.app_list(), "supported": winapi.IS_WINDOWS})

    @app.post("/api/tweaks/apps/remove")
    def tweak_remove():
        return jsonify({"results": tweaks.remove_apps([str(i) for i in body().get("ids", [])])})

    @app.post("/api/tweaks/onedrive")
    def tweak_onedrive():
        ok, msg = tweaks.uninstall_onedrive()
        return jsonify({"ok": ok, "msg": msg})

    @app.post("/api/tweaks/restore_point")
    def restore_point():
        ok, msg = winapi.create_restore_point("PyCleaner")
        return jsonify({"ok": ok, "msg": msg})

    # ── háttérmunkák ─────────────────────────────────────────────────────────
    @app.get("/api/jobs/<jid>")
    def job_status(jid):
        j = jobs.get(jid)
        return (jsonify(j), 200) if j else (jsonify({"error": t("Ismeretlen munka.")}), 404)

    # ── indítópult ───────────────────────────────────────────────────────────
    @app.get("/api/startup")
    def startup_list():
        items = startup.list_items()
        startup_cache.clear()
        startup_cache.update({i["id"]: i for i in items})
        return jsonify({"items": items, "supported": winapi.IS_WINDOWS, "is_admin": winapi.is_admin()})

    @app.post("/api/startup/toggle")
    def startup_toggle():
        b = body()
        item = startup_cache.get(int(b.get("id", -1))) if str(b.get("id", "")).isdigit() else None
        if not item:
            return jsonify({"ok": False, "msg": t("Ismeretlen elem — frissítsd a listát.")})
        ok, msg = startup.set_enabled(item, bool(b.get("enabled")))
        if ok:
            item["enabled"] = bool(b.get("enabled"))
        return jsonify({"ok": ok, "msg": msg, "item": item})

    # ── programfrissítő (winget) ─────────────────────────────────────────────
    @app.get("/api/winget")
    def winget_list():
        r = winget.list_upgrades()
        winget_cache["ids"] = {p["id"] for p in r.get("packages", []) if not p["truncated"]}
        winget_cache["count"] = len(r.get("packages", []))
        return jsonify(r)

    @app.post("/api/winget/upgrade")
    def winget_upgrade():
        ids = [str(i) for i in body().get("ids", []) if str(i) in winget_cache["ids"]]
        if not ids:
            return jsonify({"error": t("Nincs kiválasztott, frissíthető csomag — frissítsd a listát.")}), 400
        if jobs.running("winget"):
            return jsonify({"error": t("Már fut egy frissítés.")}), 409
        jid = jobs.start("winget", t("Programfrissítés"), winget.upgrade, ids)
        return jsonify({"job": jid})

    # ── programok eltávolítása ───────────────────────────────────────────────
    @app.get("/api/programs")
    def programs_list():
        items = programs.list_programs()
        program_cache.clear()
        program_cache.update({i["id"]: i for i in items})
        public = [{k: v for k, v in i.items() if k not in ("uninstall", "quiet")} for i in items]
        return jsonify({"programs": public, "supported": winapi.IS_WINDOWS, "is_admin": winapi.is_admin()})

    @app.post("/api/programs/uninstall")
    def programs_uninstall():
        b = body()
        item = program_cache.get(int(b.get("id", -1))) if str(b.get("id", "")).isdigit() else None
        if not item:
            return jsonify({"error": t("Ismeretlen program — frissítsd a listát.")}), 400
        if jobs.running("uninstall"):
            return jsonify({"error": t("Már fut egy eltávolítás.")}), 409

        def run(job, it):
            res = programs.run_uninstall(job, it)
            leftover_ok.update(os.path.normcase(os.path.abspath(x["path"])) for x in res.get("leftovers", []))
            return res
        return jsonify({"job": jobs.start("uninstall", item["name"], run, item)})

    @app.post("/api/programs/leftovers")
    def programs_leftovers():
        return jsonify({"results": programs.remove_leftovers([str(p) for p in body().get("paths", [])][:50], leftover_ok)})

    # ── gépállapot ───────────────────────────────────────────────────────────
    @app.post("/api/health/run")
    def health_run():
        running = jobs.running("health")
        if running:
            return jsonify({"job": running[0]["id"]})

        def run(job):
            d = health.collect(job)
            if winget_cache["count"] is not None and d.get("findings") is not None:
                d["winget_updates"] = winget_cache["count"]
                d["findings"] = health.evaluate(d)
                bad = sum(1 for f in d["findings"] if f["level"] == "bad")
                warn = sum(1 for f in d["findings"] if f["level"] == "warn")
                d["score"] = max(0, min(100, 100 - 15 * bad - 5 * warn))
            last_health.clear()
            last_health.update(d)
            return d
        return jsonify({"job": jobs.start("health", t("Gépállapot-felmérés"), run)})

    @app.get("/api/health/last")
    def health_last():
        return jsonify(last_health or None)

    @app.post("/api/health/open")
    def health_open():
        if not last_health:
            return jsonify({"ok": False, "msg": t("Előbb futtasd a felmérést.")})
        path = health.save_report(last_health, store.load_config().get("service"))
        import webbrowser
        from pathlib import Path
        webbrowser.open(Path(path).as_uri())
        return jsonify({"ok": True, "path": path})

    @app.get("/api/health/report")
    def health_download():
        if not last_health:
            abort(404)
        return _download(health.report_html(last_health, store.load_config().get("service")), "text/html",
                         f"gepallapot_{datetime.now():%Y%m%d_%H%M}.html")

    # ── ütemezett feladat ────────────────────────────────────────────────────
    @app.get("/api/schedule/task")
    def schedule_task():
        return jsonify(scheduler.task_status())

    # ── rendszer ─────────────────────────────────────────────────────────────
    @app.post("/api/admin/relaunch")
    def relaunch():
        if winapi.relaunch_elevated():
            threading.Thread(target=_quit, args=(hooks,), daemon=True).start()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "msg": t("Az emelt jogú indítás meg lett szakítva.")})

    @app.post("/api/open_url")
    def open_url():
        url = str(body().get("url", ""))
        base = "https://github.com/csiber/pycleaner"
        if not (url == base or url.startswith(base + "/")):
            abort(400)
        import webbrowser
        return jsonify({"ok": webbrowser.open(url)})

    @app.get("/api/update")
    def update_check():
        return jsonify(updates.check())

    @app.post("/api/exit")
    def exit_app():
        threading.Thread(target=_quit, args=(hooks,), daemon=True).start()
        return jsonify({"ok": True})

    return app


def _hostname(host: str) -> str:
    if host.startswith("["):  # [::1]:5000
        return host[: host.find("]") + 1]
    return host.split(":")[0]


def _quit(hooks: dict):
    time.sleep(0.6)
    fn = hooks.get("quit")
    if fn:
        try:
            fn()
        except Exception:  # noqa: BLE001
            pass
    os._exit(0)
