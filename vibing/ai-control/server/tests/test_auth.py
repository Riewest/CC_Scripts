import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.auth.rate_limit import login_rate_limiter
from aicontrol.config import Settings
from aicontrol.db.models import Base
from aicontrol.db.session import get_session
from aicontrol.main import create_app


@pytest.fixture
def auth_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}"

    async def create_tables() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_tables())
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app(Settings(_env_file=None, database_url=database_url, allow_signup=False))
    app.dependency_overrides[get_session] = override_session
    login_rate_limiter.clear()
    with TestClient(app) as client:
        yield client
    asyncio.run(engine.dispose())
    login_rate_limiter.clear()


def setup_admin(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/auth/setup",
        json={"username": "Admin", "password": "a-very-long-password"},
    )
    assert response.status_code == 201
    assert response.json()["username"] == "admin"
    csrf = client.cookies.get("aic_csrf")
    assert csrf
    return response.json()["id"], csrf


def test_first_user_setup_is_single_use_and_sets_secure_session_cookies(auth_client) -> None:
    state = auth_client.get("/api/auth/setup-state")
    assert state.json() == {"setup_required": True, "signup_allowed": False}

    response = auth_client.post(
        "/api/auth/setup",
        json={"username": "Admin", "password": "a-very-long-password"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    assert auth_client.get("/api/auth/setup-state").json()["setup_required"] is False
    assert auth_client.get("/api/auth/me").json()["username"] == "admin"
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith("aic_session="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("aic_csrf="))
    assert "httponly" in session_cookie.lower()
    assert "samesite=lax" in session_cookie.lower()
    assert "secure" not in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()

    duplicate = auth_client.post(
        "/api/auth/setup",
        json={"username": "another", "password": "another-long-password"},
    )
    assert duplicate.status_code == 409


def test_https_session_cookies_are_secure(auth_client) -> None:
    https_client = TestClient(auth_client.app, base_url="https://testserver")

    response = https_client.post(
        "/api/auth/setup",
        json={"username": "secure-admin", "password": "a-secure-long-password"},
    )

    assert response.status_code == 201
    cookies = response.headers.get_list("set-cookie")
    assert all("secure" in cookie.lower() for cookie in cookies)


def test_password_policy_and_signup_toggle(auth_client) -> None:
    short_password = auth_client.post(
        "/api/auth/setup", json={"username": "admin", "password": "short"}
    )
    assert short_password.status_code == 422
    setup_admin(auth_client)

    disabled_signup = auth_client.post(
        "/api/auth/register", json={"username": "second", "password": "another-long-password"}
    )
    assert disabled_signup.status_code == 403

    auth_client.app.state.settings.allow_signup = True
    enabled_signup = auth_client.post(
        "/api/auth/register", json={"username": "Second", "password": "another-long-password"}
    )
    assert enabled_signup.status_code == 201
    assert enabled_signup.json()["username"] == "second"
    assert enabled_signup.json()["role"] == "user"


def test_unknown_user_and_wrong_password_have_identical_responses(auth_client) -> None:
    setup_admin(auth_client)
    wrong_password = auth_client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    unknown_user = auth_client.post(
        "/api/auth/login", json={"username": "not-a-user", "password": "wrong-password"}
    )

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {
        "detail": "Invalid username or password"
    }


def test_login_rate_limit_blocks_repeated_failures(auth_client, monkeypatch) -> None:
    setup_admin(auth_client)
    login_rate_limiter.clear()
    monkeypatch.setattr(login_rate_limiter, "max_attempts", 2)
    for _ in range(2):
        response = auth_client.post(
            "/api/auth/login", json={"username": "admin", "password": "incorrect-password"}
        )
        assert response.status_code == 401
    blocked = auth_client.post(
        "/api/auth/login", json={"username": "admin", "password": "incorrect-password"}
    )
    assert blocked.status_code == 429


def test_unauthenticated_access_and_csrf_protection(auth_client) -> None:
    assert auth_client.get("/api/auth/me").status_code == 401
    setup_admin(auth_client)

    missing_csrf = auth_client.post("/api/auth/logout")
    assert missing_csrf.status_code == 403
    csrf = auth_client.cookies.get("aic_csrf")
    invalid_csrf = auth_client.post("/api/auth/logout", headers={"x-csrf-token": "wrong"})
    assert invalid_csrf.status_code == 403

    logout = auth_client.post("/api/auth/logout", headers={"x-csrf-token": csrf})
    assert logout.status_code == 204
    assert auth_client.get("/api/auth/me").status_code == 401


def test_change_password_revokes_all_browser_sessions(auth_client) -> None:
    setup_admin(auth_client)
    response = auth_client.post(
        "/api/auth/change-password",
        headers={"x-csrf-token": auth_client.cookies.get("aic_csrf")},
        json={
            "current_password": "a-very-long-password",
            "new_password": "a-replaced-long-password",
        },
    )

    assert response.status_code == 204
    assert auth_client.get("/api/auth/me").status_code == 401
    login = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "a-replaced-long-password"},
    )
    assert login.status_code == 200


def test_ui_websocket_requires_session_cookie_and_same_origin(auth_client) -> None:
    with pytest.raises(WebSocketDisconnect):
        with auth_client.websocket_connect("/ws/ui", headers={"origin": "http://testserver"}):
            pass

    setup_admin(auth_client)
    with auth_client.websocket_connect("/ws/ui", headers={"origin": "http://testserver"}) as websocket:
        assert websocket.receive_json() == {"type": "ready", "user": "admin"}

    with pytest.raises(WebSocketDisconnect):
        with auth_client.websocket_connect("/ws/ui", headers={"origin": "https://attacker.example"}):
            pass
