"""Tálcaikon (pystray): ablak bezárásakor a program a tálcán fut tovább, ha ez be van kapcsolva."""

import logging
import threading

log = logging.getLogger("pycleaner.tray")


class Tray:
    def __init__(self, show, quit_app, quick_clean):
        self._show, self._quit, self._quick = show, quit_app, quick_clean
        self._icon = None
        self._lock = threading.Lock()

    def ensure(self) -> bool:
        """Az ikon első szükségkor jön létre (nem kell újraindítani a beállítás után)."""
        with self._lock:
            if self._icon is not None:
                return True
            try:
                import pystray
                from PIL import Image

                from .i18n import t
                from .paths import resource_dir
                img = Image.open(resource_dir() / "static" / "favicon.png")
                menu = pystray.Menu(
                    pystray.MenuItem(t("Megnyitás"), lambda *_: self._show(), default=True),
                    pystray.MenuItem(t("Gyors tisztítás"), lambda *_: threading.Thread(target=self._run_quick, daemon=True).start()),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(t("Kilépés"), lambda *_: self._quit()),
                )
                self._icon = pystray.Icon("PyCleaner", img, "PyCleaner", menu)
                self._icon.run_detached()
                log.info("tálcaikon fut")
                return True
            except Exception as e:  # noqa: BLE001 — tálca nélkül is működjön a program
                log.warning("tálcaikon nem indult: %s", e)
                self._icon = None
                return False

    def _run_quick(self):
        from .i18n import t
        try:
            entry = self._quick()
            self.notify(t("Kész: {s} felszabadítva", s=entry["total_freed"]))
        except Exception as e:  # noqa: BLE001
            self.notify(str(e))

    def notify(self, msg: str):
        try:
            if self._icon is not None:
                self._icon.notify(msg, "PyCleaner")
        except Exception:  # noqa: BLE001
            pass

    def stop(self):
        try:
            if self._icon is not None:
                self._icon.stop()
        except Exception:  # noqa: BLE001
            pass
