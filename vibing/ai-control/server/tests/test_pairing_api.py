import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakecc import FakeCC
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.config import Settings
from aicontrol.db.models import Base, PairingCode
from aicontrol.db.security import hash_pairing_code
from aicontrol.db.session import get_session
from aicontrol.main import create_app


@pytest.fixture
def pairing_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'pairing.db').as_posix()}"

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

    app = create_app(
        Settings(
            _env_file=None,
            database_url=database_url,
            public_url="https://control.example.test",
            allow_signup=True,
        )
    )
    app.dependency_overrides[get_session] = override_session
    with TestClient(app, base_url="https://control.example.test") as client:
        yield client
    asyncio.run(engine.dispose())


def authenticate(client: TestClient) -> str:
    response = client.post(
        "/api/auth/setup",
        json={"username": "owner", "password": "a-long-setup-password"},
    )
    assert response.status_code == 201
    return client.cookies["aic_csrf"]


def test_personal_pairing_code_returns_pasteable_command_and_live_status(pairing_client) -> None:
    csrf = authenticate(pairing_client)
    response = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me", "label": "Quarry turtle"},
    )

    assert response.status_code == 201
    result = response.json()
    assert len(result["code"]) == 6
    assert all(character in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" for character in result["code"])
    assert result["command"] == (
        "wget run https://control.example.test/install?code=" + result["code"]
    )
    assert result["expires_at"].endswith("+00:00")

    status = pairing_client.get(f"/api/pairing-codes/{result['id']}")
    assert status.status_code == 200
    assert status.json()["used"] is False
    assert status.json()["paired_computer"] is None
    assert status.json()["expires_at"].endswith("+00:00")

    async def verify_persisted_secret_hash() -> None:
        engine = create_async_engine(pairing_client.app.state.settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            stored = await session.get(PairingCode, result["id"])
            assert stored is not None
            assert stored.code_hash == hash_pairing_code(result["code"])
            assert stored.code_hash != result["code"]
            expires = stored.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            assert 14 * 60 < (expires - datetime.now(UTC)).total_seconds() <= 15 * 60
        await engine.dispose()

    asyncio.run(verify_persisted_secret_hash())


def test_pairing_code_api_requires_login_csrf_and_personal_owner(pairing_client) -> None:
    unauthenticated = pairing_client.post("/api/pairing-codes", json={"owner": "me"})
    assert unauthenticated.status_code == 401
    csrf = authenticate(pairing_client)

    no_csrf = pairing_client.post("/api/pairing-codes", json={"owner": "me"})
    assert no_csrf.status_code == 403
    unknown_team = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "team-123"},
    )
    assert unknown_team.status_code == 404


def test_pairing_creation_is_rate_limited(pairing_client, monkeypatch) -> None:
    from aicontrol.pairing.rate_limit import pairing_creation_limiter

    csrf = authenticate(pairing_client)
    monkeypatch.setattr(pairing_creation_limiter, "max_attempts", 1)
    created = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me"},
    )
    blocked = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me"},
    )
    assert created.status_code == 201
    assert blocked.status_code == 429


def test_owner_can_request_identity_preserving_repair_code(pairing_client) -> None:
    csrf = authenticate(pairing_client)
    created = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me", "label": "Keep this label"},
    ).json()
    device_id = "repair-api-device"
    with FakeCC(pairing_client, device_id, created["code"]) as client:
        assert client.receive_json()["data"]["accept"] is True
        client.disconnect()

    repair = pairing_client.post(
        f"/api/computers/{device_id}/pairing-code",
        headers={"x-csrf-token": csrf},
    )
    assert repair.status_code == 201
    assert repair.json()["command"].endswith(f"?code={repair.json()['code']}")

    status = pairing_client.get(f"/api/pairing-codes/{repair.json()['id']}")
    assert status.status_code == 200
    assert status.json()["used"] is False


def test_pairing_creation_rate_limit_is_per_owner_not_global(pairing_client, monkeypatch) -> None:
    from aicontrol.pairing.rate_limit import pairing_creation_limiter

    csrf = authenticate(pairing_client)
    monkeypatch.setattr(pairing_creation_limiter, "max_attempts", 1)
    assert pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me"},
    ).status_code == 201
    assert pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me"},
    ).status_code == 429


def test_other_user_cannot_poll_pairing_status(pairing_client) -> None:
    csrf = authenticate(pairing_client)
    created = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me"},
    ).json()
    pairing_client.post("/api/auth/logout", headers={"x-csrf-token": csrf})
    register = pairing_client.post(
        "/api/auth/register",
        json={"username": "second-owner", "password": "a-second-long-password"},
    )
    assert register.status_code == 201
    assert pairing_client.get(f"/api/pairing-codes/{created['id']}").status_code == 404


def test_pairing_code_polling_is_private_to_its_owner(pairing_client) -> None:
    csrf = authenticate(pairing_client)
    code_response = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me"},
    )
    pairing_id = code_response.json()["id"]
    pairing_client.post(
        "/api/auth/logout",
        headers={"x-csrf-token": pairing_client.cookies["aic_csrf"]},
    )
    assert pairing_client.get(f"/api/pairing-codes/{pairing_id}").status_code == 401


def test_generated_command_pairs_fake_client_and_status_confirms_device(pairing_client) -> None:
    csrf = authenticate(pairing_client)
    generated = pairing_client.post(
        "/api/pairing-codes",
        headers={"x-csrf-token": csrf},
        json={"owner": "me", "label": "Registration test turtle"},
    ).json()
    device_id = "registration-flow-device"

    with FakeCC(pairing_client, device_id, generated["code"], kind="turtle") as client:
        acknowledgement = client.receive_json()
        assert acknowledgement["type"] == "hello_ack"
        assert acknowledgement["data"]["accept"] is True
        assert acknowledgement["data"]["device_secret"]
        client.disconnect()

    status = pairing_client.get(f"/api/pairing-codes/{generated['id']}")
    assert status.status_code == 200
    assert status.json()["used"] is True
    assert status.json()["paired_computer"] == {
        "id": device_id,
        "label": "Registration test turtle",
        "kind": "turtle",
        "status": "offline",
    }
