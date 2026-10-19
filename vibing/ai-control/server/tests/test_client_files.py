import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from aicontrol.config import Settings
from aicontrol.main import create_app


def test_manifest_lists_client_file_sha256_and_files_are_served() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))
    source_dir = Path(__file__).resolve().parents[2] / "client"

    response = client.get("/client/manifest.json")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["algorithm"] == "sha256"
    assert manifest["version"]
    assert ".gitkeep" not in manifest["files"]
    assert "install.lua.template" not in manifest["files"]
    assert "startup.lua" in manifest["files"]
    assert "client.lua" in manifest["files"]
    for relative_path, expected_hash in manifest["files"].items():
        body = client.get(f"/client/{relative_path}")
        assert body.status_code == 200
        assert hashlib.sha256(body.content).hexdigest() == expected_hash
        assert body.content == (source_dir / relative_path).read_bytes()


def test_manifest_file_route_rejects_unlisted_path() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/client/.env.example")

    assert response.status_code == 404


def test_install_script_embeds_server_url_and_pairing_code() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/install", params={"code": "ABC123_code"})

    assert response.status_code == 200
    assert 'local serverUrl = "http://testserver"' in response.text
    assert 'local pairingCode = "ABC123_code"' in response.text
    assert "os.reboot()" in response.text


def test_install_rejects_unsafe_pairing_code() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/install", params={"code": '";os.reboot();--'})

    assert response.status_code == 400
