from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.config import Settings
from aicontrol.db.models import (
    Base,
    Computer,
    ComputerKind,
    ControlGroup,
    GroupMember,
    Share,
    ShareRole,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from aicontrol.db.session import get_session
from aicontrol.main import create_app
from aicontrol.permissions import PermissionRole, effective_role


@pytest.fixture
def team_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'teams.db').as_posix()}"

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


def _signup(client: TestClient, username: str, *, setup: bool = False) -> tuple[str, str]:
    response = client.post(
        "/api/auth/setup" if setup else "/api/auth/register",
        json={"username": username, "password": f"a-long-{username}-password"},
    )
    assert response.status_code == 201
    if not setup:
        client.post("/api/auth/logout", headers={"x-csrf-token": client.cookies["aic_csrf"]})
        client.post(
            "/api/auth/login",
            json={"username": username, "password": f"a-long-{username}-password"},
        )
    return response.json()["id"], client.cookies["aic_csrf"]


def _team(client: TestClient, csrf: str, name="Crew", role="operator"):
    return client.post(
        "/api/teams", headers={"x-csrf-token": csrf},
        json={"name": name, "default_member_role": role},
    )


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


def test_team_lifecycle_invites_membership_leave_transfer_and_last_owner(team_client):
    owner_id, csrf = _signup(team_client, "owner", setup=True)
    team = _team(team_client, csrf).json()
    assert team["role"] == "owner"
    assert team["default_member_role"] == "operator"
    member_id, _ = _signup(team_client, "member")
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "owner", "password": "a-long-owner-password"})
    csrf = team_client.cookies["aic_csrf"]
    invite = team_client.post(
        f"/api/teams/{team['id']}/invites", headers={"x-csrf-token": csrf}, json={"username": "member"}
    )
    assert invite.status_code == 201
    secret = invite.json()["invite_token"]
    assert secret and secret not in str(team_client.get("/api/teams").json())
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "member", "password": "a-long-member-password"})
    member_csrf = team_client.cookies["aic_csrf"]
    assert team_client.get(
        "/api/teams/invites", headers={"x-csrf-token": member_csrf}
    ).json()[0]["team_id"] == team["id"]
    accepted = team_client.post(
        f"/api/teams/invites/{secret}/accept", headers={"x-csrf-token": member_csrf}
    )
    assert accepted.status_code == 201 and accepted.json()["role"] == "member"
    assert team_client.post(
        f"/api/teams/invites/{secret}/accept", headers={"x-csrf-token": member_csrf}
    ).status_code == 404
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "owner", "password": "a-long-owner-password"})
    csrf = team_client.cookies["aic_csrf"]
    assert team_client.post(
        f"/api/teams/{team['id']}/transfer-ownership", headers={"x-csrf-token": csrf}, json={"user_id": member_id}
    ).status_code == 200
    assert team_client.post(
        f"/api/teams/{team['id']}/leave", headers={"x-csrf-token": csrf}
    ).status_code == 204
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "member", "password": "a-long-member-password"})
    csrf = team_client.cookies["aic_csrf"]
    assert team_client.delete(
        f"/api/teams/{team['id']}/members/{member_id}", headers={"x-csrf-token": csrf}
    ).status_code == 409


def test_team_pairing_dashboard_permissions_and_no_ownership_transfer(team_client):
    owner_id, csrf = _signup(team_client, "owner", setup=True)
    team = _team(team_client, csrf, role="viewer").json()
    member_id, _ = _signup(team_client, "member")
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "owner", "password": "a-long-owner-password"})
    csrf = team_client.cookies["aic_csrf"]
    invite = team_client.post(
        f"/api/teams/{team['id']}/invites", headers={"x-csrf-token": csrf}, json={"username": "member"}
    ).json()
    pairing = team_client.post(
        "/api/pairing-codes", headers={"x-csrf-token": csrf},
        json={"owner": team["id"], "label": "Team turtle"},
    )
    assert pairing.status_code == 201
    code = pairing.json()["code"]
    from fakecc import FakeCC

    with FakeCC(team_client, "team-device", code) as device:
        assert device.receive_json()["type"] == "hello_ack"
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "member", "password": "a-long-member-password"})
    member_csrf = team_client.cookies["aic_csrf"]
    assert team_client.post(
        f"/api/teams/invites/{invite['invite_token']}/accept", headers={"x-csrf-token": member_csrf}
    ).status_code == 201
    computers = team_client.get("/api/computers").json()
    assert len(computers) == 1 and computers[0]["owner_team_id"] == team["id"]
    device_id = computers[0]["id"]
    assert team_client.get(f"/api/computers/{device_id}").status_code == 200
    assert team_client.post(
        f"/api/computers/{device_id}/exec", headers={"x-csrf-token": member_csrf}, json={"code": "print('no')"}
    ).status_code == 403
    assert team_client.post(
        "/api/pairing-codes", headers={"x-csrf-token": member_csrf}, json={"owner": "not-a-team"}
    ).status_code == 404
    assert team_client.patch(
        f"/api/teams/{team['id']}", headers={"x-csrf-token": member_csrf}, json={"default_member_role": "operator"}
    ).status_code == 403

    async def ownership() -> None:
        engine = create_async_engine(team_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            computer = await session.get(Computer, device_id)
            assert computer is not None
            assert computer.owner_user_id is None
            assert computer.owner_team_id == team["id"]
        await engine.dispose()

    asyncio.run(ownership())


def test_effective_role_matrix_personal_team_and_disabled(team_client):
    owner_id, _ = _signup(team_client, "owner", setup=True)
    member_id, _ = _signup(team_client, "member")
    stranger_id, _ = _signup(team_client, "stranger")

    async def verify() -> None:
        engine = create_async_engine(team_client.app.state.test_database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            owner = await session.get(User, owner_id)
            member = await session.get(User, member_id)
            stranger = await session.get(User, stranger_id)
            team = Team(name="Viewer team", slug="viewer-team", default_member_role=ShareRole.VIEWER)
            session.add(team)
            await session.flush()
            session.add_all([
                TeamMember(team_id=team.id, user_id=owner_id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=member_id, role=TeamRole.MEMBER),
            ])
            personal = Computer(id="personal", owner_user_id=owner_id, label="Personal", kind=ComputerKind.COMPUTER)
            team_pc = Computer(id="team-pc", owner_team_id=team.id, label="Team", kind=ComputerKind.COMPUTER)
            shared_pc = Computer(id="shared-pc", owner_user_id=stranger_id, label="Shared", kind=ComputerKind.COMPUTER)
            session.add_all([personal, team_pc, shared_pc])
            await session.flush()
            assert await effective_role(owner, personal, session) == PermissionRole.OWNER
            assert await effective_role(stranger, personal, session) == PermissionRole.NONE
            assert await effective_role(owner, team_pc, session) == PermissionRole.OWNER
            assert await effective_role(member, team_pc, session) == PermissionRole.VIEWER
            direct = Share(subject_user_id=member_id, computer_id=personal.id, role=ShareRole.OPERATOR)
            group = ControlGroup(name="shared group", owner_user_id=owner_id)
            session.add_all([direct, group])
            await session.flush()
            session.add(GroupMember(group_id=group.id, computer_id=shared_pc.id))
            session.add(Share(subject_team_id=team.id, group_id=group.id, role=ShareRole.OWNER))
            await session.flush()
            assert await effective_role(member, personal, session) == PermissionRole.OPERATOR
            assert await effective_role(member, shared_pc, session) == PermissionRole.OWNER
            team.default_member_role = ShareRole.OPERATOR
            await session.flush()
            assert await effective_role(member, team_pc, session) == PermissionRole.OPERATOR
            member.disabled = True
            assert await effective_role(member, team_pc, session) == PermissionRole.NONE
        await engine.dispose()

    asyncio.run(verify())


def test_personal_computer_transfer_requires_its_owner_and_is_explicit(team_client):
    owner_id, csrf = _signup(team_client, "owner", setup=True)
    team = _team(team_client, csrf, role="viewer").json()
    _personal_computers(team_client, owner_id, "move-me")
    response = team_client.post(
        f"/api/teams/{team['id']}/computers/move-me/transfer", headers={"x-csrf-token": csrf}
    )
    assert response.status_code == 200
    _signup(team_client, "stranger")
    team_client.post("/api/auth/logout", headers={"x-csrf-token": team_client.cookies["aic_csrf"]})
    team_client.post("/api/auth/login", json={"username": "stranger", "password": "a-long-stranger-password"})
    stranger_csrf = team_client.cookies["aic_csrf"]
    assert team_client.post(
        f"/api/teams/{team['id']}/computers/move-me/transfer", headers={"x-csrf-token": stranger_csrf}
    ).status_code == 404

    async def verify_ownership() -> None:
        engine = create_async_engine(team_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            computer = await session.get(Computer, "move-me")
            assert computer is not None and computer.owner_user_id is None
            assert computer.owner_team_id == team["id"]
        await engine.dispose()

    asyncio.run(verify_ownership())


def test_team_delete_requires_confirmation_and_no_team_computers(team_client):
    _, csrf = _signup(team_client, "owner", setup=True)
    team = _team(team_client, csrf).json()
    assert team_client.delete(
        f"/api/teams/{team['id']}", headers={"x-csrf-token": csrf}
    ).status_code == 422
    assert team_client.request(
        "DELETE", f"/api/teams/{team['id']}", headers={"x-csrf-token": csrf}, json={"confirm": True}
    ).status_code == 204
