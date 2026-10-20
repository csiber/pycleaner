"""Kétnyelvűség (magyar / angol). A forrásszöveg a magyar; az angol a fordítótáblából jön,
hiányzó fordításnál a magyar marad. A felület (app.js) ugyanezt a módszert használja."""

import json
import locale
import os

from .paths import SYSTEM, resource_dir

_lang: str | None = None
_en: dict[str, str] | None = None


def system_lang() -> str:
    """A Windows felhasználói nyelve (LANGID 0x0E = magyar), máshol a locale."""
    try:
        if SYSTEM == "Windows":
            import ctypes
            return "hu" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0E else "en"
        loc = os.environ.get("LANG") or (locale.getlocale()[0] or "")
        return "hu" if loc.lower().startswith("hu") else "en"
    except Exception:  # noqa: BLE001
        return "hu"


def resolve(setting: str | None) -> str:
    return setting if setting in ("hu", "en") else system_lang()


def set_lang(code: str) -> None:
    global _lang
    _lang = code if code in ("hu", "en") else "hu"


def lang() -> str:
    global _lang
    if _lang is None:
        from . import store
        _lang = resolve(store.load_config().get("language", "auto"))
    return _lang


def _table() -> dict[str, str]:
    global _en
    if _en is None:
        try:
            with open(resource_dir() / "static" / "i18n-en.json", encoding="utf-8") as f:
                _en = json.load(f)
        except (OSError, ValueError):
            _en = {}
    return _en


def t(text: str, **kw) -> str:
    """Fordítás + {név} helyettesítés: t("{n} fájl törölve", n=3)."""
    out = _table().get(text, text) if lang() == "en" else text
    return out.format(**kw) if kw else out
