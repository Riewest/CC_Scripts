from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.config import Settings
from aicontrol.db.models import (
    Base,
    Computer,
    ComputerKind,
    Share,
)
from aicontrol.db.session import get_session
from aicontrol.main import create_app


@pytest.fixture
def sharing_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'sharing.db').as_posix()}"

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


def _signup(client: TestClient, username: str, setup=False) -> tuple[str, str]:
    response = client.post(
        "/api/auth/setup" if setup else "/api/auth/register",
        json={"username": username, "password": f"a-long-{username}-password"},
    )
    assert response.status_code == 201
    if not setup:
        client.post("/api/auth/logout", headers={"x-csrf-token": client.cookies["aic_csrf"]})
        client.post("/api/auth/login", json={"username": username, "password": f"a-long-{username}-password"})
    return response.json()["id"], client.cookies["aic_csrf"]


def _computer(client: TestClient, owner_id: str, computer_id: str) -> None:
    async def seed() -> None:
        engine = create_async_engine(client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            session.add(Computer(id=computer_id, owner_user_id=owner_id, label=computer_id, kind=ComputerKind.COMPUTER))
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())


def _login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": f"a-long-{username}-password"}
    )
    assert response.status_code == 200
    return client.cookies["aic_csrf"]


def test_group_crud_membership_and_permission_inheritance(sharing_client):
    owner_id, owner_csrf = _signup(sharing_client, "owner", setup=True)
    viewer_id, _ = _signup(sharing_client, "viewer")
    _computer(sharing_client, owner_id, "first")
    _computer(sharing_client, owner_id, "second")
    owner_csrf = _login(sharing_client, "owner")
    group = sharing_client.post(
        "/api/groups", headers={"x-csrf-token": owner_csrf}, json={"name": "Fleet"}
    )
    assert group.status_code == 201
    group_id = group.json()["id"]
    add_first = sharing_client.post(
        f"/api/groups/{group_id}/computers", headers={"x-csrf-token": owner_csrf}, json={"computer_id": "first"}
    )
    assert add_first.status_code == 201
    assert sharing_client.post(
        f"/api/groups/{group_id}/computers", headers={"x-csrf-token": owner_csrf}, json={"computer_id": "first"}
    ).status_code == 409
    grant = sharing_client.post(
        "/api/shares", headers={"x-csrf-token": owner_csrf},
        json={"subject_user_id": viewer_id, "group_id": group_id, "role": "viewer"},
    )
    assert grant.status_code == 201
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": sharing_client.cookies["aic_csrf"]})
    sharing_client.post("/api/auth/login", json={"username": "viewer", "password": "a-long-viewer-password"})
    viewer_csrf = sharing_client.cookies["aic_csrf"]
    computers = sharing_client.get("/api/computers").json()
    assert [computer["id"] for computer in computers] == ["first"]
    assert computers[0]["effective_role"] == "viewer"
    assert sharing_client.get("/api/computers/first/runs").status_code == 200
    assert sharing_client.post(
        "/api/computers/first/exec", headers={"x-csrf-token": viewer_csrf}, json={"code": "print('no')"}
    ).status_code == 403
    assert sharing_client.get("/api/groups", headers={"x-csrf-token": viewer_csrf}).json()[0]["id"] == group_id
    assert sharing_client.delete(
        f"/api/groups/{group_id}/computers/first", headers={"x-csrf-token": viewer_csrf}
    ).status_code == 404
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": viewer_csrf})
    sharing_client.post("/api/auth/login", json={"username": "owner", "password": "a-long-owner-password"})
    owner_csrf = sharing_client.cookies["aic_csrf"]
    assert sharing_client.patch(
        f"/api/groups/{group_id}", headers={"x-csrf-token": owner_csrf}, json={"name": "Updated Fleet"}
    ).status_code == 200
    assert sharing_client.delete(
        f"/api/groups/{group_id}/computers/first", headers={"x-csrf-token": owner_csrf}
    ).status_code == 204
    assert sharing_client.delete(
        f"/api/shares/{grant.json()['id']}", headers={"x-csrf-token": owner_csrf}
    ).status_code == 204


def test_direct_share_roles_highest_grant_and_owner_revoke(sharing_client):
    owner_id, csrf = _signup(sharing_client, "owner", setup=True)
    viewer_id, _ = _signup(sharing_client, "viewer")
    _computer(sharing_client, owner_id, "control")
    csrf = _login(sharing_client, "owner")
    viewer_share = sharing_client.post(
        "/api/shares", headers={"x-csrf-token": csrf},
        json={"subject_user_id": viewer_id, "computer_id": "control", "role": "viewer"},
    ).json()
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": sharing_client.cookies["aic_csrf"]})
    sharing_client.post("/api/auth/login", json={"username": "viewer", "password": "a-long-viewer-password"})
    csrf = sharing_client.cookies["aic_csrf"]
    assert sharing_client.get("/api/computers/control").json()["effective_role"] == "viewer"
    operator_share = sharing_client.post(
        "/api/auth/login", json={"username": "viewer", "password": "a-long-viewer-password"}
    )
    assert operator_share.status_code == 200
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": sharing_client.cookies["aic_csrf"]})
    sharing_client.post("/api/auth/login", json={"username": "owner", "password": "a-long-owner-password"})
    csrf = sharing_client.cookies["aic_csrf"]
    elevated = sharing_client.post(
        "/api/shares", headers={"x-csrf-token": csrf},
        json={"subject_user_id": viewer_id, "computer_id": "control", "role": "operator"},
    ).json()
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": csrf})
    sharing_client.post("/api/auth/login", json={"username": "viewer", "password": "a-long-viewer-password"})
    csrf = sharing_client.cookies["aic_csrf"]
    assert sharing_client.get("/api/computers/control").json()["effective_role"] == "operator"
    assert sharing_client.delete(
        f"/api/shares/{elevated['id']}", headers={"x-csrf-token": csrf}
    ).status_code == 404
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": csrf})
    sharing_client.post("/api/auth/login", json={"username": "owner", "password": "a-long-owner-password"})
    csrf = sharing_client.cookies["aic_csrf"]
    assert sharing_client.delete(
        f"/api/shares/{elevated['id']}", headers={"x-csrf-token": csrf}
    ).status_code == 204
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": csrf})
    sharing_client.post("/api/auth/login", json={"username": "viewer", "password": "a-long-viewer-password"})
    assert sharing_client.get("/api/computers/control").json()["effective_role"] == "viewer"
    assert sharing_client.delete(
        f"/api/shares/{viewer_share['id']}", headers={"x-csrf-token": sharing_client.cookies["aic_csrf"]}
    ).status_code == 404


def test_group_owner_share_grants_group_administration(sharing_client):
    owner_id, owner_csrf = _signup(sharing_client, "owner", setup=True)
    group_owner_id, _ = _signup(sharing_client, "groupowner")
    _computer(sharing_client, owner_id, "group-owned-device")
    owner_csrf = _login(sharing_client, "owner")
    group = sharing_client.post(
        "/api/groups", headers={"x-csrf-token": owner_csrf}, json={"name": "Owner grant"}
    ).json()
    sharing_client.post(
        f"/api/groups/{group['id']}/computers", headers={"x-csrf-token": owner_csrf},
        json={"computer_id": "group-owned-device"},
    )
    owner_grant = sharing_client.post(
        "/api/shares", headers={"x-csrf-token": owner_csrf},
        json={"subject_user_id": group_owner_id, "group_id": group["id"], "role": "owner"},
    )
    assert owner_grant.status_code == 201
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": owner_csrf})
    sharing_client.post("/api/auth/login", json={"username": "groupowner", "password": "a-long-groupowner-password"})
    group_csrf = sharing_client.cookies["aic_csrf"]
    assert sharing_client.get("/api/computers/group-owned-device").json()["effective_role"] == "owner"
    assert sharing_client.patch(
        f"/api/groups/{group['id']}", headers={"x-csrf-token": group_csrf}, json={"name": "Managed group"}
    ).status_code == 200
    assert sharing_client.delete(
        f"/api/groups/{group['id']}/computers/group-owned-device", headers={"x-csrf-token": group_csrf}
    ).status_code == 204
    assert sharing_client.delete(
        f"/api/shares/{owner_grant.json()['id']}", headers={"x-csrf-token": group_csrf}
    ).status_code == 404


def test_revoke_closes_live_ui_socket_within_revalidation_period(sharing_client, monkeypatch):
    from aicontrol.auth import websocket as websocket_module

    owner_id, csrf = _signup(sharing_client, "owner", setup=True)
    viewer_id, _ = _signup(sharing_client, "viewer")
    _computer(sharing_client, owner_id, "live")
    csrf = _login(sharing_client, "owner")
    share = sharing_client.post(
        "/api/shares", headers={"x-csrf-token": csrf},
        json={"subject_user_id": viewer_id, "computer_id": "live", "role": "viewer"},
    ).json()
    monkeypatch.setattr(websocket_module, "SESSION_REVALIDATE_INTERVAL", 0.05)
    sharing_client.post("/api/auth/logout", headers={"x-csrf-token": sharing_client.cookies["aic_csrf"]})
    sharing_client.post("/api/auth/login", json={"username": "viewer", "password": "a-long-viewer-password"})
    socket = sharing_client.websocket_connect("/ws/ui", headers={"origin": "http://testserver"})
    with socket as websocket:
        assert websocket.receive_json()["type"] == "ready"
        def revoke() -> None:
            async def remove() -> None:
                engine = create_async_engine(sharing_client.app.state.test_database_url)
                factory = async_sessionmaker(engine)
                async with factory() as session:
                    share_record = await session.get(Share, share["id"])
                    await session.delete(share_record)
                    await session.commit()
                await engine.dispose()
            asyncio.run(remove())
        worker = threading.Thread(target=revoke)
        worker.start()
        worker.join()
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()


def test_share_validation_rejects_bad_recipients_or_target_and_token_group_access_is_current(sharing_client):
    owner_id, csrf = _signup(sharing_client, "owner", setup=True)
    _computer(sharing_client, owner_id, "shared")
    assert sharing_client.post(
        "/api/shares", headers={"x-csrf-token": csrf},
        json={"subject_user_id": "missing", "computer_id": "shared", "role": "viewer"},
    ).status_code == 404
    assert sharing_client.post(
        "/api/shares", headers={"x-csrf-token": csrf},
        json={"subject_user_id": owner_id, "subject_team_id": "bad", "computer_id": "shared", "role": "viewer"},
    ).status_code == 422
    group = sharing_client.post(
        "/api/groups", headers={"x-csrf-token": csrf}, json={"name": "Restricted"}
    ).json()
    assert sharing_client.post(
        f"/api/groups/{group['id']}/computers", headers={"x-csrf-token": csrf}, json={"computer_id": "shared"}
    ).status_code == 201
