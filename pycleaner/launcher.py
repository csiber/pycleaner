"""Indító: szabad port, Flask-szerver háttérszálon, natív ablak (pywebview) vagy böngésző."""

import argparse
import logging
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

from . import APP_NAME, __version__, scheduler
from .paths import data_dir


def free_port(preferred: int = 0) -> int:
    for port in ([preferred] if preferred else []) + [0]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    raise RuntimeError("Nincs szabad port.")


def _serve(app, port: int):
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", port, app, threaded=True)
    threading.Thread(target=srv.serve_forever, name="pycleaner-http", daemon=True).start()
    return srv


def _wait_ready(url: str, timeout: float = 10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url + "favicon.ico", timeout=1).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


def _setup_logging(console: bool):
    handlers = [logging.FileHandler(data_dir() / "pycleaner.log", encoding="utf-8")]
    if console:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pycleaner", description=f"{APP_NAME} {__version__}")
    ap.add_argument("--browser", action="store_true", help="natív ablak helyett az alapértelmezett böngészőben nyílik")
    ap.add_argument("--no-open", action="store_true", help="csak a szerver indul (fejlesztéshez)")
    ap.add_argument("--port", type=int, default=0, help="rögzített port (alapból véletlen szabad port)")
    ap.add_argument("--auto-clean", action="store_true", help="ütemezett tisztítás ablak nélkül (a Feladatütemező hívja)")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = ap.parse_args(argv)

    has_console = sys.stdout is not None and not getattr(sys, "frozen", False)
    _setup_logging(has_console)
    log = logging.getLogger("pycleaner")

    if args.auto_clean:
        sys.exit(scheduler.auto_clean())

    from .server import create_app
    token = secrets.token_urlsafe(32)
    hooks: dict = {}
    app = create_app(token, hooks=hooks)
    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    srv = _serve(app, port)
    scheduler.start()
    log.info("%s %s fut: %s (adatok: %s)", APP_NAME, __version__, url, data_dir())

    if args.no_open:
        print(f"{APP_NAME} {__version__} — {url}  (Ctrl+C a leállításhoz)")
        _block()
        return

    if not args.browser and _run_native(url, hooks, log):
        srv.shutdown()
        os._exit(0)

    # böngészős mód: a „Kilépés” gomb állítja le a folyamatot
    _wait_ready(url)
    webbrowser.open(url)
    if has_console:
        print(f"{APP_NAME} {__version__} — {url}\nA felületen a Kilépés gombbal vagy Ctrl+C-vel állítható le.")
    _block()


def _block():
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        os._exit(0)


def _run_native(url: str, hooks: dict, log) -> bool:
    """Natív ablak pywebview-val (Windowson Edge WebView2). False, ha nem érhető el."""
    try:
        import webview
    except ImportError:
        log.info("pywebview nem elérhető, böngészős mód")
        return False
    try:
        win = webview.create_window(APP_NAME, url, width=1320, height=860, min_size=(1000, 660),
                                    background_color="#101216", text_select=True)

        def pick_folder():
            res = win.create_file_dialog(webview.FOLDER_DIALOG)
            return res[0] if res else None

        from . import cleaner, store
        from .i18n import t
        from .tray import Tray
        state = {"quitting": False, "told": False}

        def quit_app():
            state["quitting"] = True
            tray.stop()
            win.destroy()

        def show():
            win.show()
            win.restore()

        def quick_clean():
            ids = [c["id"] for c in cleaner.category_meta() if c["default"] and not c["locked"]]
            return cleaner.clean(ids)

        tray = Tray(show, quit_app, quick_clean)

        def on_closing():
            # bezáráskor a tálcára kerül, ha a Beállításokban kérték (és a tálcaikon elindult)
            if not state["quitting"] and store.load_config().get("close_to_tray") and tray.ensure():
                win.hide()
                if not state["told"]:
                    tray.notify(t("A PyCleaner a tálcán fut tovább. Kilépés: jobb klikk az ikonon."))
                    state["told"] = True
                return False
            tray.stop()
            return True

        win.events.closing += on_closing
        if store.load_config().get("close_to_tray"):
            tray.ensure()
        hooks.update(native=True, pick_folder=pick_folder, quit=quit_app)
        if hasattr(webview, "settings"):
            webview.settings["ALLOW_DOWNLOADS"] = True
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        _wait_ready(url)
        webview.start(lambda: log.info("natív ablak fut (%s)", getattr(webview, "renderer", "?")),
                      private_mode=False, storage_path=str(data_dir() / "webview"))
        return True
    except Exception as e:  # noqa: BLE001 — pl. hiányzó WebView2 runtime
        log.warning("natív ablak nem indult (%s), böngészős mód", e)
        hooks.clear()
        return False


if __name__ == "__main__":
    main()
