import json
import os
import time
from datetime import datetime, timedelta

from pycleaner import duplicates, scheduler, store
from pycleaner.registry import command_executable
from pycleaner.updates import _parse


def test_command_executable():
    assert command_executable('"C:\\Program Files\\A B\\x.exe" --min') == "C:\\Program Files\\A B\\x.exe"
    assert command_executable("C:\\Program Files\\Foo\\bar.exe /silent") == "C:\\Program Files\\Foo\\bar.exe"
    assert command_executable("notepad") is None
    assert command_executable("") is None


def test_password_hashing():
    h = store.hash_password("titok")
    assert h.startswith("pbkdf2$") and "titok" not in h
    assert store.check_password(h, "titok")
    assert not store.check_password(h, "rossz")
    assert store.check_password("", "bármi")


def test_legacy_plaintext_password_is_migrated(data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config.json").write_text(json.dumps({
        "theme": "dark", "active_profile": "default",
        "profiles": {"default": {"name": "Régi", "password": "1234", "color_accent": "#00c8f0"}}}), encoding="utf-8")
    cfg = store.load_config()
    prof = cfg["profiles"]["default"]
    assert "password" not in prof and store.check_password(prof["password_hash"], "1234")
    pub = store.public_config()["profiles"]["default"]
    assert pub["has_password"] is True and "password_hash" not in pub


def test_profile_switch_requires_password():
    pid = store.create_profile("Család")
    store.update_profile(pid, {"password": "abc"})
    store.switch_profile("default")
    assert not store.switch_profile(pid, "rossz")
    assert store.switch_profile(pid, "abc")
    assert store.load_config()["active_profile"] == pid


def test_profile_input_validation():
    store.update_profile("default", {"accent": "red;}", "backup_max_mb": 10 ** 9, "name": "x" * 100})
    p = store.active_profile()
    assert p["accent"] != "red;}" and p["backup_max_mb"] == 10_000 and len(p["name"]) == 40


def test_duplicates(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "sub" / "b.bin"
    c = tmp_path / "c.bin"
    b.parent.mkdir()
    data = os.urandom(200_000)
    a.write_bytes(data)
    b.write_bytes(data)
    c.write_bytes(data[:-1] + b"!")  # azonos méret, más tartalom
    old = time.time() - 86400
    os.utime(a, (old, old))
    r = duplicates.find(str(tmp_path), min_size_kb=1)
    assert len(r["groups"]) == 1
    assert [f["path"] for f in r["groups"][0]["files"]] == [str(b), str(a)]  # a legújabb elöl
    assert r["total_wasted"] == 200_000


def test_scheduler_due():
    now = datetime(2026, 1, 2, 12)
    assert not scheduler.due({"enabled": False}, now)
    assert scheduler.due({"enabled": True, "last_run": None}, now)
    assert scheduler.due({"enabled": True, "interval_hours": 24, "last_run": (now - timedelta(hours=25)).isoformat()}, now)
    assert not scheduler.due({"enabled": True, "interval_hours": 24, "last_run": (now - timedelta(hours=2)).isoformat()}, now)


def test_schedule_rejects_unknown_categories():
    s = store.save_schedule({"enabled": True, "interval_hours": 0, "categories": ["temp", "rm -rf"]})
    assert s["categories"] == ["temp"] and s["interval_hours"] == 1


def test_version_parse():
    assert _parse("v5.0.1") > _parse("5.0.0")
    assert _parse("5.10.0") > _parse("5.9.9")
