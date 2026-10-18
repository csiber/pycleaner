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

from . import (__version__, analyzer, cleaner, duplicates, monitor, registry, report, scheduler, store,
               tweaks, updates, winapi)
from .paths import backups_dir, data_dir, registry_backups_dir, resource_dir

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def create_app(token: str | None = None, *, hooks: dict | None = None) -> Flask:
    res = resource_dir()
    app = Flask("pycleaner", template_folder=str(res / "templates"), static_folder=str(res / "static"))
    app.config["TOKEN"] = token or secrets.token_urlsafe(32)
    app.config["JSON_SORT_KEYS"] = False
    app.json.ensure_ascii = False
    hooks = hooks or {}
    offered: set[str] = set()          # törölhető útvonalak (amiket mi listáztunk)
    offered_lock = threading.Lock()
    reg_cache: dict[int, dict] = {}

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
        return render_template("index.html", token=app.config["TOKEN"], version=__version__,
                               native=bool(hooks.get("native")))

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder, "favicon.ico")

    # ── alapadatok ───────────────────────────────────────────────────────────
    @app.get("/api/bootstrap")
    def bootstrap():
        return jsonify({"version": __version__, "system": monitor.system_info(),
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
            return jsonify({"error": "A mappa nem létezik."}), 400
        items = analyzer.large_files(root, float(b.get("min_mb", 100) or 100))
        offer(i["path"] for i in items)
        return jsonify({"root": root, "files": items})

    @app.post("/api/duplicates")
    def find_duplicates():
        b = body()
        root = _root(b)
        if not root:
            return jsonify({"error": "A mappa nem létezik."}), 400
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
                out.append({"path": p, "ok": False, "error": "Ezt a fájlt nem a PyCleaner listázta."})
                continue
            try:
                if not os.path.isfile(p) or os.path.islink(p):
                    raise FileNotFoundError("A fájl már nem létezik.")
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
                out.append({"id": i, "ok": False, "msg": "Ismeretlen elem — futtasd újra a keresést."})
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
        s = store.save_schedule(b)
        if s["enabled"]:
            scheduler.start()
        return jsonify(s)

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
            return jsonify({"error": "Adj nevet a profilnak."}), 400
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
            return jsonify({"ok": False, "msg": "A mappa nem létezik."})
        if cleaner.is_protected(p):
            return jsonify({"ok": False, "msg": "Ez rendszer- vagy személyes mappa, ezt nem engedem üríteni."})
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
        ok, msg = winapi.create_restore_point("PyCleaner — módosítás előtt")
        return jsonify({"ok": ok, "msg": msg})

    # ── rendszer ─────────────────────────────────────────────────────────────
    @app.post("/api/admin/relaunch")
    def relaunch():
        if winapi.relaunch_elevated():
            threading.Thread(target=_quit, args=(hooks,), daemon=True).start()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "msg": "Az emelt jogú indítás meg lett szakítva."})

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
