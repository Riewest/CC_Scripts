from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from aicontrol.db.models import (
    AiMessage,
    AiProvider,
    AiSession,
    ApiToken,
    AuditEvent,
    Computer,
    ComputerKind,
    ComputerStatus,
    ControlGroup,
    Goal,
    GoalStep,
    GroupMember,
    PairingCode,
    Script,
    ScriptVersion,
    Share,
    ShareRole,
    Team,
    TeamMember,
    TeamRole,
    User,
    UserIdentity,
    UserRole,
    utc_now,
)
from aicontrol.db.security import (
    decrypt_provider_key,
    encrypt_provider_key,
    hash_secret,
    verify_secret,
)


@pytest.mark.asyncio
async def test_user_and_computer_crud(db_session) -> None:
    user = User(username="pilot", password_hash=hash_secret("a-long-password"), role=UserRole.USER)
    db_session.add(user)
    await db_session.flush()
    computer = Computer(
        owner_user_id=user.id,
        label="Workshop",
        kind=ComputerKind.COMPUTER,
        status=ComputerStatus.OFFLINE,
        device_secret_hash=hash_secret("device-secret"),
    )
    db_session.add(computer)
    await db_session.commit()

    stored = await db_session.scalar(select(Computer).where(Computer.id == computer.id))

    assert stored is not None
    assert stored.owner_user.username == "pilot"
    assert verify_secret(stored.owner_user.password_hash, "a-long-password")
    assert verify_secret(stored.device_secret_hash, "device-secret")
    await db_session.delete(stored)
    await db_session.commit()


@pytest.mark.asyncio
async def test_owner_constraint_requires_exactly_one_owner(db_session) -> None:
    db_session.add(Computer(label="Unowned", kind=ComputerKind.COMPUTER))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    user = User(username="owner")
    team = Team(name="Team", slug="team")
    db_session.add_all([user, team])
    await db_session.flush()
    db_session.add(
        Computer(
            owner_user_id=user.id,
            owner_team_id=team.id,
            label="Double-owned",
            kind=ComputerKind.TURTLE,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_all_domain_models_support_crud(db_session) -> None:
    user = User(username="model-user")
    team = Team(name="Model Team", slug="model-team")
    db_session.add_all([user, team])
    await db_session.flush()
    computer = Computer(owner_user_id=user.id, label="Turtle", kind=ComputerKind.TURTLE)
    group = ControlGroup(name="Fleet", owner_user_id=user.id)
    script = Script(owner_user_id=user.id, name="Routine")
    provider = AiProvider(
        owner_user_id=user.id,
        name="Local provider",
        provider_type="openai-compatible",
        encrypted_api_key="encrypted",
    )
    db_session.add_all([computer, group, script, provider])
    await db_session.flush()
    session = AiSession(computer=computer, provider=provider, title="Chat")
    goal = Goal(computer=computer, created_by_user_id=user.id, title="Explore")
    db_session.add_all([session, goal])
    await db_session.flush()

    records = [
        UserIdentity(user=user, issuer="https://issuer.test", subject="subject"),
        TeamMember(team=team, user=user, role=TeamRole.OWNER),
        PairingCode(code_hash=hash_secret("pairing"), owner_user_id=user.id, expires_at=utc_now() + timedelta(minutes=5)),
        GroupMember(group=group, computer=computer),
        Share(subject_user_id=user.id, computer=computer, role=ShareRole.OPERATOR),
        ScriptVersion(script=script, version=1, content="print('hi')", computer=computer),
        ApiToken(user=user, token_hash=hash_secret("api-token"), label="test token"),
        AuditEvent(actor=user, action="test", details={"ok": True}),
        AiMessage(session=session, role="user", content="Hello"),
        GoalStep(goal=goal, sequence=1, action="inspect"),
    ]
    db_session.add_all(records)
    await db_session.commit()

    for model in (
        UserIdentity,
        TeamMember,
        PairingCode,
        GroupMember,
        Share,
        ScriptVersion,
        ApiToken,
        AuditEvent,
        AiMessage,
        GoalStep,
    ):
        assert await db_session.scalar(select(model)) is not None



def test_secrets_are_hashed_and_provider_keys_encrypted(monkeypatch) -> None:
    secret_hash = hash_secret("secret-value")
    assert secret_hash != "secret-value"
    assert verify_secret(secret_hash, "secret-value")
    assert not verify_secret(secret_hash, "wrong-value")

    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("AIC_SECRET_ENCRYPTION_KEY", key)
    from aicontrol.config import get_settings

    get_settings.cache_clear()
    encrypted = encrypt_provider_key("provider-api-key")
    assert encrypted != "provider-api-key"
    assert decrypt_provider_key(encrypted) == "provider-api-key"
    get_settings.cache_clear()
