import pytest


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Minden teszt saját, üres adatmappát kap — a valódi beállításokhoz nem nyúlunk."""
    d = tmp_path / "data"
    monkeypatch.setenv("PYCLEANER_DATA", str(d))
    return d
