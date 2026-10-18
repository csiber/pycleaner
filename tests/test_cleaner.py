import os
from pathlib import Path

from pycleaner import cleaner, store


def all_targets():
    return [t.path for ts in cleaner._targets().values() for t in ts]


def test_firefox_profile_root_is_never_a_target():
    # v4-ben a teljes Firefox-profil (jelszavak, könyvjelzők) a törlendők között volt
    for p in all_targets():
        norm = p.replace("\\", "/").rstrip("/")
        if "Firefox/Profiles" in norm or norm.endswith(".mozilla/firefox"):
            assert norm.endswith("cache2"), p


def test_no_target_is_protected():
    for p in all_targets():
        assert not cleaner.is_protected(p), p


def test_protected_paths():
    assert cleaner.is_protected(str(Path.home()))
    assert cleaner.is_protected(os.path.abspath(os.sep))
    assert cleaner.is_protected(str(Path.home() / "Documents"))


def test_custom_dirs_filter_protected(tmp_path):
    ok = tmp_path / "cache"
    ok.mkdir()
    store.update_profile("default", {"custom_dirs": [str(ok), str(Path.home()), "/nincs/ilyen"]})
    assert cleaner.custom_dirs() == [str(ok)]


def test_clean_custom_category_end_to_end(tmp_path):
    junk = tmp_path / "junk"
    (junk / "sub").mkdir(parents=True)
    (junk / "a.bin").write_bytes(b"1" * 1000)
    (junk / "sub" / "b.bin").write_bytes(b"2" * 24)
    store.update_profile("default", {"custom_dirs": [str(junk)]})
    assert cleaner.scan()["custom"]["size"] == 1024
    entry = cleaner.clean(["custom"])
    assert entry["total_freed_bytes"] == 1024 and entry["total_files"] == 2
    assert list(junk.iterdir()) == []
    assert store.load_history()[0]["total_freed_bytes"] == 1024


def test_backup_is_made_and_pruned(tmp_path):
    junk = tmp_path / "junk"
    junk.mkdir()
    store.update_profile("default", {"custom_dirs": [str(junk)], "auto_backup": True, "backup_keep": 2})
    names = []
    for i in range(3):
        (junk / f"f{i}.txt").write_text("hello")
        e = cleaner.clean(["custom"])
        names.append(e["backup"])
        assert e["backup"]
    from pycleaner.paths import backups_dir
    assert len(list(backups_dir().glob("backup_*.zip"))) <= 2


def test_unknown_categories_are_ignored():
    e = cleaner.clean(["nincs_ilyen"])
    assert e["details"] == []
