from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.audit import record, redact
from aicontrol.config import Settings
from aicontrol.db.models import (
    AuditEvent,
    Base,
    Computer,
    ComputerKind,
    Share,
    ShareRole,
)
from aicontrol.db.session import get_session
from aicontrol.main import create_app


@pytest.fixture
def audit_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'audit.db').as_posix()}"

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


def _setup(client: TestClient) -> tuple[str, str]:
    response = client.post("/api/auth/setup", json={"username": "admin", "password": "a-very-long-password"})
    assert response.status_code == 201
    return response.json()["id"], client.cookies["aic_csrf"]


def _insert(client: TestClient, event: AuditEvent) -> None:
    async def insert() -> None:
        engine = create_async_engine(client.app.state.test_database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(event)
            await session.commit()
        await engine.dispose()

    asyncio.run(insert())


def test_redaction_masks_secret_fields_bearer_values_and_inline_secrets():
    value = redact({
        "password": "never-store-this",
        "nested": {"api_key": "another-secret", "message": "Bearer abcdefghijklmnop aic_abcdefghijklmnop"},
        "code": "password = 'inline-secret'\nprint('ok')",
    })
    serialized = str(value)
    assert "never-store-this" not in serialized
    assert "another-secret" not in serialized
    assert "abcdefghijklmnop" not in serialized
    assert "inline-secret" not in serialized
    assert "[REDACTED]" in serialized


def test_exec_and_auth_actions_are_audited_with_redacted_code_and_result(audit_client, monkeypatch):
    user_id, csrf = _setup(audit_client)

    async def seed_computer() -> None:
        engine = create_async_engine(audit_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            computer = Computer(id="audit-device", owner_user_id=user_id, label="Audit device", kind=ComputerKind.COMPUTER)
            session.add(computer)
            await session.flush()
            computer.status = "online"
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_computer())
    from aicontrol.protocol.models import ExecResultMessage

    async def fake_call(*_args, **_kwargs):
        return ExecResultMessage(
            type="exec_result", id="test-run", reply_to="test-run",
            data={"ok": True, "output": "Bearer supersecretbearervalue", "return_values": [], "duration_ms": 1},
        )

    monkeypatch.setattr(audit_client.app.state.gateway.registry, "call", fake_call)
    response = audit_client.post(
        "/api/computers/audit-device/exec",
        headers={"x-csrf-token": csrf},
        json={"code": "local password = 'inline-password-secret'\nprint('safe')"},
    )
    assert response.status_code == 200
    assert audit_client.post(
        "/api/computers/audit-device/interrupt", headers={"x-csrf-token": csrf}
    ).status_code in {202, 409}
    audit_client.post("/api/auth/logout", headers={"x-csrf-token": csrf})
    audit_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    csrf = audit_client.cookies["aic_csrf"]

    events = audit_client.get("/api/audit", headers={"x-csrf-token": csrf}).json()["items"]
    actions = [event["action"] for event in events]
    assert "auth.setup" in actions
    assert "computer.exec" in actions
    run_event = next(event for event in events if event["action"] == "computer.exec")
    serialized = str(run_event["details"])
    assert "inline-password-secret" not in serialized
    assert "supersecretbearervalue" not in serialized
    assert run_event["computer_id"] == "audit-device"
    assert run_event["source_ip"]


def test_audit_visibility_operator_sees_only_own_events_and_owner_sees_all(audit_client):
    owner_id, csrf = _setup(audit_client)
    audit_client.post("/api/auth/register", json={"username": "operator", "password": "another-long-password"})
    operator_id = audit_client.get("/api/auth/me").json()["id"]

    async def seed() -> None:
        engine = create_async_engine(audit_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            computer = Computer(id="visibility-device", owner_user_id=owner_id, label="Visibility", kind=ComputerKind.COMPUTER)
            computer_id = computer.id
            session.add(computer)
            await session.flush()
            session.add(Share(subject_user_id=operator_id, computer_id=computer_id, role=ShareRole.OPERATOR))
            await record(session, action="exec.owner", actor_user_id=owner_id, computer_id=computer_id, details={"code": "owner"}, commit=False)
            await record(session, action="exec.operator", actor_user_id=operator_id, computer_id=computer_id, details={"code": "operator"}, commit=False)
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())
    audit_client.post("/api/auth/logout", headers={"x-csrf-token": audit_client.cookies["aic_csrf"]})
    audit_client.post("/api/auth/login", json={"username": "operator", "password": "another-long-password"})
    operator_csrf = audit_client.cookies["aic_csrf"]
    operator_events = audit_client.get("/api/audit?computer_id=visibility-device", headers={"x-csrf-token": operator_csrf}).json()
    assert [event["action"] for event in operator_events["items"]] == ["exec.operator"]
    audit_client.post("/api/auth/logout", headers={"x-csrf-token": operator_csrf})
    audit_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    owner_events = audit_client.get("/api/audit?computer_id=visibility-device", headers={"x-csrf-token": audit_client.cookies["aic_csrf"]}).json()
    assert {event["action"] for event in owner_events["items"]} == {"exec.owner", "exec.operator"}


def test_audit_pagination_filters_and_json_csv_export(audit_client):
    user_id, csrf = _setup(audit_client)
    for index in range(5):
        _insert(audit_client, AuditEvent(actor_user_id=user_id, action="test.action" if index % 2 == 0 else "other.action", outcome="success" if index % 2 == 0 else "failure", details={"index": index}))
    first = audit_client.get("/api/audit?action=test.action&limit=2&offset=0", headers={"x-csrf-token": csrf}).json()
    assert first["total"] == 3 and first["has_more"] is True and len(first["items"]) == 2
    second = audit_client.get("/api/audit?action=test.action&limit=2&offset=2", headers={"x-csrf-token": csrf}).json()
    assert second["has_more"] is False and len(second["items"]) == 1
    json_export = audit_client.get("/api/audit/export?format=json&action=test.action", headers={"x-csrf-token": csrf})
    assert json_export.status_code == 200 and len(json_export.json()) == 3
    csv_export = audit_client.get("/api/audit/export?format=csv&action=test.action", headers={"x-csrf-token": csrf})
    rows = list(csv.DictReader(io.StringIO(csv_export.text)))
    assert len(rows) == 3 and rows[0]["action"] == "test.action"


def test_csv_export_neutralizes_formula_cells(audit_client):
    user_id, csrf = _setup(audit_client)
    _insert(audit_client, AuditEvent(actor_user_id=user_id, action="=HYPERLINK('https://bad')", details={"note": "=cmd"}))
    response = audit_client.get("/api/audit/export?format=csv", headers={"x-csrf-token": csrf})
    row = next(csv.DictReader(io.StringIO(response.text)))
    assert row["action"].startswith("'=")
    assert row["details"].startswith("'")


def test_audit_is_immutable_and_retention_prune_is_admin_only(audit_client):
    user_id, csrf = _setup(audit_client)
    event = AuditEvent(actor_user_id=user_id, action="old.event", created_at=datetime.now(UTC) - timedelta(days=10))
    _insert(audit_client, event)

    async def mutation_checks() -> None:
        engine = create_async_engine(audit_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            existing = await session.get(AuditEvent, event.id)
            existing.action = "changed"
            with pytest.raises(ValueError, match="append-only"):
                await session.commit()
            await session.rollback()
            existing = await session.get(AuditEvent, event.id)
            await session.delete(existing)
            with pytest.raises(ValueError, match="retention"):
                await session.commit()
            await session.rollback()
        await engine.dispose()

    asyncio.run(mutation_checks())
    audit_client.post("/api/auth/register", json={"username": "normal", "password": "another-long-password"})
    audit_client.post("/api/auth/logout", headers={"x-csrf-token": audit_client.cookies["aic_csrf"]})
    audit_client.post("/api/auth/login", json={"username": "normal", "password": "another-long-password"})
    assert audit_client.delete(
        "/api/audit/retention?before=" + (datetime.now(UTC) - timedelta(days=5)).isoformat().replace("+00:00", "Z"),
        headers={"x-csrf-token": audit_client.cookies["aic_csrf"]},
    ).status_code == 403
    audit_client.post("/api/auth/logout", headers={"x-csrf-token": audit_client.cookies["aic_csrf"]})
    audit_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    pruned = audit_client.delete(
        "/api/audit/retention?before=" + (datetime.now(UTC) - timedelta(days=5)).isoformat().replace("+00:00", "Z"),
        headers={"x-csrf-token": audit_client.cookies["aic_csrf"]},
    )
    assert pruned.status_code == 204
    actions = [event["action"] for event in audit_client.get("/api/audit", headers={"x-csrf-token": audit_client.cookies["aic_csrf"]}).json()["items"]]
    assert "audit.retention_pruned" in actions
    assert "old.event" not in actions


def test_team_share_token_admin_and_pairing_mutations_are_audited(audit_client):
    owner_id, csrf = _setup(audit_client)
    audit_client.post("/api/auth/register", json={"username": "second", "password": "another-long-password"})
    second_id = audit_client.get("/api/auth/me").json()["id"]
    audit_client.post("/api/auth/logout", headers={"x-csrf-token": audit_client.cookies["aic_csrf"]})
    audit_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    csrf = audit_client.cookies["aic_csrf"]
    team = audit_client.post("/api/teams", headers={"x-csrf-token": csrf}, json={"name": "Audited team"})
    assert team.status_code == 201
    team_id = team.json()["id"]
    invite = audit_client.post(
        f"/api/teams/{team_id}/invites", headers={"x-csrf-token": csrf}, json={"username": "second"}
    )
    assert invite.status_code == 201
    assert invite.json()["invite_token"] not in str(
        audit_client.get("/api/audit", headers={"x-csrf-token": csrf}).json()
    )
    token = audit_client.post(
        "/api/auth/tokens", headers={"x-csrf-token": csrf}, json={"label": "audited", "scopes": ["computers:read"]}
    )
    assert token.status_code == 201
    bearer = token.json()["token"]
    assert audit_client.get("/api/auth/me", headers={"Authorization": f"Bearer {bearer}"}).status_code == 200
    assert audit_client.delete(
        f"/api/auth/tokens/{token.json()['id']}", headers={"x-csrf-token": csrf}
    ).status_code == 204
    changed = audit_client.patch(
        f"/api/admin/users/{second_id}", headers={"x-csrf-token": csrf}, json={"disabled": True}
    )
    assert changed.status_code == 200
    events = audit_client.get("/api/audit", headers={"x-csrf-token": csrf}).json()["items"]
    actions = {event["action"] for event in events}
    assert {"team.create", "team.invite_create", "api_token.create", "api_token.use", "api_token.revoke", "admin.user_update"} <= actions
    assert all(bearer not in str(event) for event in events)

    _computer(audit_client, owner_id, "pairing-audit-device")
    pairing = audit_client.post(
        "/api/computers/pairing-audit-device/pairing-code", headers={"x-csrf-token": csrf}
    )
    assert pairing.status_code == 201
    newest = audit_client.get("/api/audit?action=pairing.repair_create", headers={"x-csrf-token": csrf}).json()["items"]
    assert newest and newest[0]["computer_id"] == "pairing-audit-device"
    assert pairing.json()["code"] not in str(newest)


def _computer(client: TestClient, owner_id: str, computer_id: str) -> None:
    async def seed() -> None:
        engine = create_async_engine(client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            session.add(Computer(id=computer_id, owner_user_id=owner_id, label=computer_id, kind=ComputerKind.COMPUTER))
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())
