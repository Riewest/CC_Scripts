from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.auth.sessions import API_TOKEN_LABEL_PREFIX, token_digest
from aicontrol.config import Settings
from aicontrol.db.models import ApiToken, Base, Computer, ComputerKind
from aicontrol.db.session import get_session
from aicontrol.main import create_app


@pytest.fixture
def token_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'tokens.db').as_posix()}"

    async def create_tables() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_tables())
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator:
        async with factory() as session:
            yield session

    app = create_app(Settings(_env_file=None, database_url=database_url, allow_signup=True))
    app.state.test_database_url = database_url
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client
    asyncio.run(engine.dispose())


def _admin(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/auth/setup", json={"username": "admin", "password": "a-very-long-password"}
    )
    assert response.status_code == 201
    return response.json()["id"], client.cookies["aic_csrf"]


def _create_token(client: TestClient, csrf: str, **overrides):
    request = {"label": "automation", "scopes": ["computers:read"], **overrides}
    return client.post("/api/auth/tokens", headers={"x-csrf-token": csrf}, json=request)


def _personal_computers(client: TestClient, user_id: str, *ids: str) -> None:
    async def seed() -> None:
        engine = create_async_engine(client.app.state.test_database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            for computer_id in ids:
                session.add(
                    Computer(
                        id=computer_id,
                        owner_user_id=user_id,
                        label=f"Computer {computer_id}",
                        kind=ComputerKind.COMPUTER,
                    )
                )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())


def test_token_shown_once_hash_only_and_metadata_updates(token_client):
    user_id, csrf = _admin(token_client)
    _personal_computers(token_client, user_id, "allowed", "other")
    response = _create_token(token_client, csrf, computer_ids=["allowed"])
    assert response.status_code == 201
    created = response.json()
    secret = created["token"]
    assert secret.startswith("aic_")
    assert len(secret) > 40
    assert created["prefix"] == secret[:12]
    assert "token" not in token_client.get("/api/auth/tokens", headers={"x-csrf-token": csrf}).json()[0]

    async def persisted() -> None:
        engine = create_async_engine(token_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            record = await session.scalar(select(ApiToken).where(ApiToken.token_hash == token_digest(secret)))
            assert record is not None
            assert record.token_hash != secret
            assert record.label == API_TOKEN_LABEL_PREFIX + "automation"
            assert record.scopes == ["computers:read"]
            assert record.computer_ids == ["allowed"]
        await engine.dispose()

    asyncio.run(persisted())
    bearer = {"Authorization": f"Bearer {secret}"}
    assert token_client.get("/api/auth/me", headers=bearer).status_code == 200
    assert [item["id"] for item in token_client.get("/api/computers", headers=bearer).json()] == ["allowed"]

    async def used() -> None:
        engine = create_async_engine(token_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            record = await session.scalar(select(ApiToken).where(ApiToken.token_hash == token_digest(secret)))
            assert record is not None
            assert record.last_used_at is not None
            assert record.last_used_ip
        await engine.dispose()

    asyncio.run(used())


def test_token_scope_and_computer_restrictions_apply_to_every_computer_endpoint(token_client):
    user_id, csrf = _admin(token_client)
    _personal_computers(token_client, user_id, "allowed", "other")
    created = _create_token(token_client, csrf, computer_ids=["allowed"]).json()
    headers = {"Authorization": f"Bearer {created['token']}"}
    assert token_client.get("/api/computers/allowed", headers=headers).status_code == 200
    assert token_client.get("/api/computers/other", headers=headers).status_code == 403
    assert token_client.get("/api/computers/other/runs", headers=headers).status_code == 403
    assert token_client.post("/api/computers/allowed/exec", headers=headers, json={"code": "print('x')"}).status_code == 403
    assert token_client.post("/api/computers/allowed/interrupt", headers=headers).status_code == 403
    assert token_client.post("/api/computers/allowed/emergency-stop", headers=headers).status_code == 403
    assert token_client.post("/api/computers/allowed/reboot", headers=headers).status_code == 403


def test_exec_scope_does_not_grant_read_scope_or_admin_scope(token_client):
    user_id, csrf = _admin(token_client)
    _personal_computers(token_client, user_id, "owned")
    created = _create_token(token_client, csrf, scopes=["computers:exec"]).json()
    headers = {"Authorization": f"Bearer {created['token']}"}
    assert token_client.get("/api/computers", headers=headers).status_code == 403
    assert token_client.get("/api/admin/users", headers=headers).status_code == 403
    assert token_client.post("/api/computers/owned/exec", headers=headers, json={"code": "print('x')"}).status_code == 409


def test_admin_scope_is_limited_to_admin_user_and_admin_scope_does_not_replace_read(token_client):
    user_id, csrf = _admin(token_client)
    token = _create_token(token_client, csrf, scopes=["admin"]).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert token_client.get("/api/admin/users", headers=headers).status_code == 200
    assert token_client.get("/api/computers", headers=headers).status_code == 403


def test_revoked_and_expired_tokens_are_rejected_immediately(token_client):
    _, csrf = _admin(token_client)
    created = _create_token(token_client, csrf).json()
    headers = {"Authorization": f"Bearer {created['token']}"}
    assert token_client.get("/api/auth/me", headers=headers).status_code == 200
    assert token_client.delete(
        f"/api/auth/tokens/{created['id']}", headers={"x-csrf-token": csrf}
    ).status_code == 204
    assert token_client.get("/api/auth/me", headers=headers).status_code == 401

    expiring = _create_token(token_client, csrf).json()
    secret = expiring["token"]

    async def expire() -> None:
        engine = create_async_engine(token_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            record = await session.get(ApiToken, expiring["id"])
            assert record is not None
            record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        await engine.dispose()

    asyncio.run(expire())
    assert token_client.get("/api/auth/me", headers={"Authorization": f"Bearer {secret}"}).status_code == 401


def test_token_creation_rejects_invalid_expiry_scope_resources_and_csrf(token_client):
    user_id, csrf = _admin(token_client)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert _create_token(token_client, csrf, expires_at=past).status_code == 422
    assert _create_token(token_client, csrf, scopes=["unknown"]).status_code == 422
    assert _create_token(token_client, csrf, computer_ids=["not-owned"]).status_code == 404
    assert token_client.post("/api/auth/tokens", json={"label": "x", "scopes": ["computers:read"]}).status_code == 403
    assert token_client.post(
        "/api/auth/tokens", headers={"x-csrf-token": csrf},
        json={"label": "admin", "scopes": ["admin"]},
    ).status_code == 201


def test_normal_user_cannot_create_admin_scoped_token(token_client):
    _admin(token_client)
    token_client.post("/api/auth/logout", headers={"x-csrf-token": token_client.cookies["aic_csrf"]})
    assert token_client.post(
        "/api/auth/register", json={"username": "normal", "password": "another-long-password"}
    ).status_code == 201
    response = _create_token(
        token_client, token_client.cookies["aic_csrf"], scopes=["admin"]
    )
    assert response.status_code == 403
