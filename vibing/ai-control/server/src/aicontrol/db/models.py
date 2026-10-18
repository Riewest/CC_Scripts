from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    USER = "user"


class ComputerKind(enum.StrEnum):
    COMPUTER = "computer"
    TURTLE = "turtle"
    POCKET = "pocket"


class ComputerStatus(enum.StrEnum):
    OFFLINE = "offline"
    ONLINE = "online"


class TeamRole(enum.StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class ShareRole(enum.StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    OWNER = "owner"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_username", "username", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    identities: Mapped[list[UserIdentity]] = relationship(back_populates="user", cascade="all, delete-orphan")
    team_memberships: Mapped[list[TeamMember]] = relationship(back_populates="user", cascade="all, delete-orphan")
    computers: Mapped[list[Computer]] = relationship(back_populates="owner_user")
    api_tokens: Mapped[list[ApiToken]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserIdentity(TimestampMixin, Base):
    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_identity_issuer_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    user: Mapped[User] = relationship(back_populates="identities")


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (Index("ix_teams_slug", "slug", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    memberships: Mapped[list[TeamMember]] = relationship(back_populates="team", cascade="all, delete-orphan")
    computers: Mapped[list[Computer]] = relationship(back_populates="owner_team")


class TeamMember(TimestampMixin, Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[TeamRole] = mapped_column(Enum(TeamRole), default=TeamRole.MEMBER, nullable=False)
    team: Mapped[Team] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="team_memberships")


class Computer(TimestampMixin, Base):
    __tablename__ = "computers"
    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL AND owner_team_id IS NULL) OR "
            "(owner_user_id IS NULL AND owner_team_id IS NOT NULL)",
            name="ck_computer_exactly_one_owner",
        ),
        Index("ix_computers_owner_user_id", "owner_user_id"),
        Index("ix_computers_owner_team_id", "owner_team_id"),
        Index("ix_computers_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[ComputerKind] = mapped_column(Enum(ComputerKind), nullable=False)
    advanced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cc_version: Mapped[str | None] = mapped_column(String(80))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ComputerStatus] = mapped_column(
        Enum(ComputerStatus), default=ComputerStatus.OFFLINE, nullable=False
    )
    device_secret_hash: Mapped[str | None] = mapped_column(String(255))
    owner_user: Mapped[User | None] = relationship(back_populates="computers")
    owner_team: Mapped[Team | None] = relationship(back_populates="computers")
    shares: Mapped[list[Share]] = relationship(back_populates="computer", cascade="all, delete-orphan")
    script_versions: Mapped[list[ScriptVersion]] = relationship(back_populates="computer")
    ai_sessions: Mapped[list[AiSession]] = relationship(back_populates="computer")
    goals: Mapped[list[Goal]] = relationship(back_populates="computer")


class PairingCode(TimestampMixin, Base):
    __tablename__ = "pairing_codes"
    __table_args__ = (Index("ix_pairing_codes_expires_at", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    owner_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ControlGroup(TimestampMixin, Base):
    __tablename__ = "groups"
    __table_args__ = (Index("ix_groups_owner_user_id", "owner_user_id"), Index("ix_groups_owner_team_id", "owner_team_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    members: Mapped[list[GroupMember]] = relationship(back_populates="group", cascade="all, delete-orphan")
    shares: Mapped[list[Share]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupMember(TimestampMixin, Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "computer_id", name="uq_group_computer"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    computer_id: Mapped[str] = mapped_column(ForeignKey("computers.id", ondelete="CASCADE"), nullable=False, index=True)
    group: Mapped[ControlGroup] = relationship(back_populates="members")
    computer: Mapped[Computer] = relationship()


class Share(TimestampMixin, Base):
    __tablename__ = "shares"
    __table_args__ = (
        CheckConstraint(
            "(subject_user_id IS NOT NULL AND subject_team_id IS NULL) OR "
            "(subject_user_id IS NULL AND subject_team_id IS NOT NULL)",
            name="ck_share_exactly_one_subject",
        ),
        CheckConstraint(
            "(computer_id IS NOT NULL AND group_id IS NULL) OR "
            "(computer_id IS NULL AND group_id IS NOT NULL)",
            name="ck_share_exactly_one_target",
        ),
        Index("ix_shares_subject_user_id", "subject_user_id"),
        Index("ix_shares_subject_team_id", "subject_team_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    computer_id: Mapped[str | None] = mapped_column(ForeignKey("computers.id", ondelete="CASCADE"))
    group_id: Mapped[str | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    role: Mapped[ShareRole] = mapped_column(Enum(ShareRole), nullable=False)
    computer: Mapped[Computer | None] = relationship(back_populates="shares")
    group: Mapped[ControlGroup | None] = relationship(back_populates="shares")


class Script(TimestampMixin, Base):
    __tablename__ = "scripts"
    __table_args__ = (Index("ix_scripts_owner_user_id", "owner_user_id"), Index("ix_scripts_owner_team_id", "owner_team_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    versions: Mapped[list[ScriptVersion]] = relationship(back_populates="script", cascade="all, delete-orphan")


class ScriptVersion(TimestampMixin, Base):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("script_id", "version", name="uq_script_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    script_id: Mapped[str] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    computer_id: Mapped[str | None] = mapped_column(ForeignKey("computers.id", ondelete="SET NULL"), index=True)
    script: Mapped[Script] = relationship(back_populates="versions")
    computer: Mapped[Computer | None] = relationship(back_populates="script_versions")


class ApiToken(TimestampMixin, Base):
    __tablename__ = "api_tokens"
    __table_args__ = (Index("ix_api_tokens_token_hash", "token_hash", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="api_tokens")


class AuditEvent(TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_actor_user_id", "actor_user_id"), Index("ix_audit_events_created_at", "created_at"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    actor: Mapped[User | None] = relationship()


class AiProvider(TimestampMixin, Base):
    __tablename__ = "ai_providers"
    __table_args__ = (Index("ix_ai_providers_owner_user_id", "owner_user_id"), Index("ix_ai_providers_owner_team_id", "owner_team_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(80), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sessions: Mapped[list[AiSession]] = relationship(back_populates="provider")


class AiSession(TimestampMixin, Base):
    __tablename__ = "ai_sessions"
    __table_args__ = (Index("ix_ai_sessions_computer_id", "computer_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    computer_id: Mapped[str] = mapped_column(ForeignKey("computers.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("ai_providers.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(String(200))
    autonomy_mode: Mapped[str | None] = mapped_column(String(40))
    computer: Mapped[Computer] = relationship(back_populates="ai_sessions")
    provider: Mapped[AiProvider | None] = relationship(back_populates="sessions")
    messages: Mapped[list[AiMessage]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AiMessage(TimestampMixin, Base):
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_session_created_at", "session_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    session: Mapped[AiSession] = relationship(back_populates="messages")


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (Index("ix_goals_computer_id", "computer_id"), Index("ix_goals_status", "status"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    computer_id: Mapped[str] = mapped_column(ForeignKey("computers.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    computer: Mapped[Computer] = relationship(back_populates="goals")
    steps: Mapped[list[GoalStep]] = relationship(back_populates="goal", cascade="all, delete-orphan")


class GoalStep(TimestampMixin, Base):
    __tablename__ = "goal_steps"
    __table_args__ = (UniqueConstraint("goal_id", "sequence", name="uq_goal_step_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    goal: Mapped[Goal] = relationship(back_populates="steps")
