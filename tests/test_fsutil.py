import os
import sys
import time

import pytest

from pycleaner.fsutil import candidates, clean_dir, fmt, measure


def touch(p, size=10, age_days=0):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
    return p


def test_fmt():
    assert fmt(0) == "0 B"
    assert fmt(512) == "512 B"
    assert fmt(2048) == "2,0 KB"
    assert fmt(5 * 1024 ** 2) == "5,0 MB"
    assert fmt(3.5 * 1024 ** 3) == "3,50 GB"


def test_clean_dir_removes_files_and_prunes_dirs(tmp_path):
    touch(tmp_path / "a.tmp", 100)
    touch(tmp_path / "sub" / "deep" / "b.tmp", 50)
    removed, errors, freed = clean_dir(str(tmp_path))
    assert (removed, errors, freed) == (2, 0, 150)
    assert list(tmp_path.iterdir()) == []
    assert tmp_path.exists()  # a mappa maga megmarad


def test_measure_matches_clean(tmp_path):
    touch(tmp_path / "old.log", 30, age_days=10)
    touch(tmp_path / "new.log", 40)
    touch(tmp_path / "old.txt", 50, age_days=10)
    rules = {"min_age_days": 7, "suffixes": (".log",)}
    assert measure(str(tmp_path), **rules) == (30, 1)
    assert clean_dir(str(tmp_path), 7, (".log",))[2] == 30
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.log", "old.txt"]


def test_prefix_and_hidden_rules(tmp_path):
    touch(tmp_path / "thumbcache_32.db")
    touch(tmp_path / "other.db")
    touch(tmp_path / ".X11-unix" / "X0")
    names = {os.path.basename(p) for p, _ in candidates(str(tmp_path), prefix=("thumbcache_",), skip_hidden_top=True)}
    assert names == {"thumbcache_32.db"}


@pytest.mark.skipif(sys.platform == "win32", reason="symlink jog kell hozzá Windowson")
def test_symlinks_are_never_followed(tmp_path):
    outside = tmp_path / "outside"
    keep = touch(outside / "precious.txt")
    target = tmp_path / "target"
    target.mkdir()
    (target / "dirlink").symlink_to(outside, target_is_directory=True)
    (target / "filelink").symlink_to(keep)
    removed, _e, _f = clean_dir(str(target))
    assert removed == 0
    assert keep.exists()
    assert (target / "dirlink").is_symlink() and (target / "filelink").is_symlink()


@pytest.mark.skipif(sys.platform == "win32", reason="symlink jog kell hozzá Windowson")
def test_symlinked_root_is_refused(tmp_path):
    real = tmp_path / "real"
    touch(real / "x.tmp")
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    assert clean_dir(str(tmp_path / "link")) == (0, 0, 0)
    assert (real / "x.tmp").exists()
