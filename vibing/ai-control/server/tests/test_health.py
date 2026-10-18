from fastapi.testclient import TestClient

from aicontrol.config import Settings
from aicontrol.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AIC_HOST", "127.0.0.1")
    monkeypatch.setenv("AIC_PORT", "8123")
    monkeypatch.setenv("AIC_ENVIRONMENT", "test")

    settings = Settings(_env_file=None)

    assert settings.host == "127.0.0.1"
    assert settings.port == 8123
    assert settings.environment == "test"


def test_spa_fallback_serves_built_ui(tmp_path) -> None:
    (tmp_path / "index.html").write_text("<main>AI Control</main>", encoding="utf-8")
    client = TestClient(create_app(Settings(_env_file=None, web_dist_dir=tmp_path)))

    response = client.get("/computers/example")

    assert response.status_code == 200
    assert "AI Control" in response.text
