import pytest

from pycleaner import server


@pytest.fixture
def client():
    app = server.create_app("teszt-token")
    return app.test_client()


H = {"X-PyCleaner-Token": "teszt-token"}


def test_index_embeds_token_and_csp(client):
    r = client.get("/", base_url="http://127.0.0.1:5000")
    assert r.status_code == 200
    assert b'content="teszt-token"' in r.data
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


def test_api_requires_token(client):
    assert client.get("/api/history", base_url="http://127.0.0.1:5000").status_code == 403
    assert client.get("/api/history", headers={"X-PyCleaner-Token": "rossz"}, base_url="http://127.0.0.1:5000").status_code == 403
    assert client.get("/api/history", headers=H, base_url="http://127.0.0.1:5000").status_code == 200
    assert client.get("/api/history?t=teszt-token", base_url="http://127.0.0.1:5000").status_code == 200


def test_foreign_host_is_rejected(client):
    # DNS-rebinding ellen: hiába jó a token, idegen Host fejléccel nem szolgál ki
    assert client.get("/api/history", headers=H, base_url="http://evil.example:5000").status_code == 403
    assert client.get("/", base_url="http://evil.example:5000").status_code == 403
    assert client.get("/", base_url="http://localhost:5000").status_code == 200


def test_delete_only_offered_files(client, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr("pycleaner.fsutil.send_to_trash", lambda p: trashed.append(p))
    big = tmp_path / "big.bin"
    big.write_bytes(b"0" * (2 * 1024 * 1024))
    other = tmp_path / "secret.txt"
    other.write_text("nem listázott")
    base = "http://127.0.0.1:5000"
    r = client.post("/api/files/delete", json={"paths": [str(big)]}, headers=H, base_url=base).get_json()
    assert r["results"][0]["ok"] is False  # még nem ajánlottuk fel
    found = client.post("/api/large_files", json={"path": str(tmp_path), "min_mb": 1}, headers=H, base_url=base).get_json()
    assert [f["name"] for f in found["files"]] == ["big.bin"]
    r = client.post("/api/files/delete", json={"paths": [str(big), str(other)]}, headers=H, base_url=base).get_json()
    assert [x["ok"] for x in r["results"]] == [True, False]
    assert trashed == [str(big)]


def test_open_url_restricted(client):
    base = "http://127.0.0.1:5000"
    assert client.post("/api/open_url", json={"url": "https://evil.example"}, headers=H, base_url=base).status_code == 400
    assert client.post("/api/open_url", json={"url": "https://github.com/csiber/pycleanerX"}, headers=H, base_url=base).status_code == 400


def test_backup_name_validation(client):
    base = "http://127.0.0.1:5000"
    assert client.get("/api/backups/file/..%2Fconfig.json", headers=H, base_url=base).status_code == 404
    r = client.post("/api/backups/delete", json={"name": "../config.json"}, headers=H, base_url=base)
    assert r.status_code == 400


def test_custom_dir_validation(client, tmp_path):
    base = "http://127.0.0.1:5000"
    from pathlib import Path
    assert not client.post("/api/config/validate_dir", json={"path": str(Path.home())}, headers=H, base_url=base).get_json()["ok"]
    assert client.post("/api/config/validate_dir", json={"path": str(tmp_path)}, headers=H, base_url=base).get_json()["ok"]


def test_report_escapes_html():
    from pycleaner import report
    html = report.build([{"timestamp": "<script>alert(1)</script>", "categories": ["<b>x</b>"], "total_freed": "1 B",
                          "total_freed_bytes": 1, "total_files": 1}])
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html
