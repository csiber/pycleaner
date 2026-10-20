import pytest


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Minden teszt saját, üres adatmappát kap — a valódi beállításokhoz nem nyúlunk —,
    és magyar nyelven indul (a gép rendszernyelvétől függetlenül)."""
    from pycleaner import i18n
    d = tmp_path / "data"
    monkeypatch.setenv("PYCLEANER_DATA", str(d))
    i18n.set_lang("hu")
    yield d
    i18n.set_lang("hu")
