"""JSON-alapú tárolás: beállítások/profilok, előzmények, ütemezés. Atomikus írás, szálbiztos."""

import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime

from .paths import data_dir

_lock = threading.RLock()

DEFAULT_PROFILE = {
    "name": "Alapértelmezett",
    "password_hash": "",
    "accent": "#2bb8e8",
    "custom_dirs": [],
    "auto_backup": False,
    "backup_max_mb": 200,
    "backup_keep": 5,
}

DEFAULT_CONFIG = {
    "theme": "system",
    "language": "auto",
    "close_to_tray": False,
    "service": {"name": "", "contact": "", "note": ""},
    "active_profile": "default",
    "check_updates": True,
    "profiles": {"default": copy.deepcopy(DEFAULT_PROFILE)},
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "use_task": False,
    "interval_hours": 24,
    "categories": ["temp", "browser", "crash"],
    "last_run": None,
}


def _path(name: str) -> str:
    return os.path.join(data_dir(), name)


def _read(name: str, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return copy.deepcopy(default)


def _write(name: str, data) -> None:
    p = _path(name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


# ── jelszó ────────────────────────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"


def check_password(stored: str, pw: str) -> bool:
    if not stored:
        return True
    try:
        _alg, salt, digest = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(dk.hex(), digest)


# ── beállítások ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    with _lock:
        cfg = _read("config.json", DEFAULT_CONFIG)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, copy.deepcopy(v))
        profiles = cfg.setdefault("profiles", {})
        profiles.setdefault("default", copy.deepcopy(DEFAULT_PROFILE))
        for prof in profiles.values():
            # v4 → v5 átállás: a régi, sima szöveges jelszót hash-eljük
            legacy = prof.pop("password", "")
            if legacy and legacy != "***" and not prof.get("password_hash"):
                prof["password_hash"] = hash_password(legacy)
            for drop in ("color_accent", "color_accent2", "notify_toast"):
                prof.pop(drop, None)
            for k, v in DEFAULT_PROFILE.items():
                prof.setdefault(k, copy.deepcopy(v))
        if cfg.get("active_profile") not in profiles:
            cfg["active_profile"] = "default"
        if cfg.get("theme") not in ("system", "dark", "light"):
            cfg["theme"] = "system"
        return cfg


def save_config(cfg: dict) -> None:
    with _lock:
        _write("config.json", cfg)


def active_profile() -> dict:
    cfg = load_config()
    return cfg["profiles"][cfg["active_profile"]]


def public_config() -> dict:
    """A felületnek küldött változat: jelszó-hash helyett csak egy jelző."""
    cfg = load_config()
    for prof in cfg["profiles"].values():
        prof["has_password"] = bool(prof.pop("password_hash", ""))
    return cfg


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def update_profile(pid: str, changes: dict) -> None:
    with _lock:
        cfg = load_config()
        prof = cfg["profiles"][pid]
        if "name" in changes:
            prof["name"] = str(changes["name"])[:40].strip() or prof["name"]
        if "accent" in changes and _HEX.match(str(changes["accent"])):
            prof["accent"] = changes["accent"]
        if "auto_backup" in changes:
            prof["auto_backup"] = bool(changes["auto_backup"])
        for key, lo, hi in (("backup_max_mb", 10, 10_000), ("backup_keep", 1, 100)):
            if key in changes:
                try:
                    prof[key] = max(lo, min(hi, int(changes[key])))
                except (TypeError, ValueError):
                    pass
        if "custom_dirs" in changes and isinstance(changes["custom_dirs"], list):
            prof["custom_dirs"] = [str(d).strip() for d in changes["custom_dirs"] if str(d).strip()][:50]
        if "password" in changes:
            pw = str(changes["password"])
            prof["password_hash"] = hash_password(pw) if pw else ""
        save_config(cfg)


def create_profile(name: str) -> str:
    with _lock:
        cfg = load_config()
        base = re.sub(r"\W+", "_", name.lower()).strip("_") or "profil"
        pid, n = base, 2
        while pid in cfg["profiles"]:
            pid, n = f"{base}_{n}", n + 1
        prof = copy.deepcopy(DEFAULT_PROFILE)
        prof["name"] = name[:40] or "Új profil"
        cfg["profiles"][pid] = prof
        cfg["active_profile"] = pid
        save_config(cfg)
        return pid


def delete_profile(pid: str) -> bool:
    with _lock:
        cfg = load_config()
        if pid == "default" or pid not in cfg["profiles"]:
            return False
        del cfg["profiles"][pid]
        cfg["active_profile"] = "default"
        save_config(cfg)
        return True


def switch_profile(pid: str, password: str = "") -> bool:
    with _lock:
        cfg = load_config()
        prof = cfg["profiles"].get(pid)
        if prof is None or not check_password(prof.get("password_hash", ""), password):
            return False
        cfg["active_profile"] = pid
        save_config(cfg)
        return True


def set_option(key: str, value) -> None:
    with _lock:
        cfg = load_config()
        if key == "theme" and value in ("system", "dark", "light"):
            cfg["theme"] = value
        elif key in ("check_updates", "close_to_tray"):
            cfg[key] = bool(value)
        elif key == "language" and value in ("auto", "hu", "en"):
            cfg["language"] = value
            from . import i18n
            i18n.set_lang(i18n.resolve(value))
        elif key == "service" and isinstance(value, dict):
            cfg["service"] = {"name": str(value.get("name", ""))[:80], "contact": str(value.get("contact", ""))[:300],
                              "note": str(value.get("note", ""))[:1000]}
        save_config(cfg)


# ── előzmények ────────────────────────────────────────────────────────────────

def load_history() -> list:
    with _lock:
        h = _read("history.json", [])
        return h if isinstance(h, list) else []


def add_history(entry: dict) -> None:
    with _lock:
        h = load_history()
        h.insert(0, entry)
        _write("history.json", h[:200])


def clear_history() -> None:
    with _lock:
        _write("history.json", [])


# ── ütemezés ──────────────────────────────────────────────────────────────────

def load_schedule() -> dict:
    with _lock:
        s = _read("schedule.json", DEFAULT_SCHEDULE)
        for k, v in DEFAULT_SCHEDULE.items():
            s.setdefault(k, copy.deepcopy(v))
        return s


def save_schedule(s: dict) -> dict:
    from .cleaner import CATEGORY_IDS
    with _lock:
        cur = load_schedule()
        if "enabled" in s:
            cur["enabled"] = bool(s["enabled"])
        if "use_task" in s:
            cur["use_task"] = bool(s["use_task"])
        if "interval_hours" in s:
            try:
                cur["interval_hours"] = max(1, min(24 * 30, int(s["interval_hours"])))
            except (TypeError, ValueError):
                pass
        if "categories" in s and isinstance(s["categories"], list):
            cur["categories"] = [c for c in s["categories"] if c in CATEGORY_IDS]
        if "last_run" in s:
            cur["last_run"] = s["last_run"]
        _write("schedule.json", cur)
        return cur


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
