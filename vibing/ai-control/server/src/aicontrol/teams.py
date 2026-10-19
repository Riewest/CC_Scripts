from __future__ import annotations

import re
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import SessionPrincipal, require_csrf, token_digest
from aicontrol.db.models import (
    Computer,
    ShareRole,
    Team,
    TeamInvite,
    TeamMember,
    TeamRole,
    User,
    utc_now,
)
from aicontrol.db.session import get_session

router = APIRouter(prefix="/api/teams", tags=["teams"])
INVITE_LIFETIME = timedelta(days=7)


class TeamCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    default_member_role: ShareRole = ShareRole.OPERATOR

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("Team name cannot be blank")
        return result

    @field_validator("default_member_role")
    @classmethod
    def member_role_cannot_own(cls, value: ShareRole) -> ShareRole:
        if value == ShareRole.OWNER:
            raise ValueError("Team default member role must be viewer or operator")
        return value


class InviteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().casefold()


class MemberRemove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


class TeamRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_member_role: ShareRole

    @field_validator("default_member_role")
    @classmethod
    def member_role_cannot_own(cls, value: ShareRole) -> ShareRole:
        if value == ShareRole.OWNER:
            raise ValueError("Team default member role must be viewer or operator")
        return value


class TeamDeleteConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool


def _team_payload(team: Team, membership: TeamMember) -> dict[str, object]:
    return {
        "id": team.id,
        "name": team.name,
        "slug": team.slug,
        "default_member_role": team.default_member_role.value,
        "role": membership.role.value,
        "member_count": len(team.memberships),
    }


async def _membership(session: AsyncSession, team_id: str, user_id: str) -> tuple[Team, TeamMember]:
    team = await session.get(Team, team_id)
    membership = await session.scalar(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    if team is None or membership is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team, membership


def _require_owner(membership: TeamMember) -> None:
    if membership.role != TeamRole.OWNER:
        raise HTTPException(status_code=403, detail="Team owner access required")


@router.get("")
async def list_teams(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    memberships = await session.scalars(
        select(TeamMember).where(TeamMember.user_id == principal.user.id)
    )
    result = []
    for membership in memberships:
        team = await session.get(Team, membership.team_id)
        if team:
            await session.refresh(team, attribute_names=["memberships"])
            result.append(_team_payload(team, membership))
    return result


@router.get("/{team_id}/members")
async def list_members(
    team_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, str]]:
    _, _ = await _membership(session, team_id, principal.user.id)
    memberships = await session.scalars(
        select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.created_at)
    )
    result = []
    for membership in memberships:
        user = await session.get(User, membership.user_id)
        if user:
            result.append({"user_id": user.id, "username": user.username, "role": membership.role.value})
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    slug_base = re.sub(r"[^a-z0-9]+", "-", payload.name.casefold()).strip("-")[:60] or "team"
    team = Team(name=payload.name, slug=f"{slug_base}-{secrets.token_hex(4)}", default_member_role=payload.default_member_role)
    session.add(team)
    await session.flush()
    membership = TeamMember(team_id=team.id, user_id=principal.user.id, role=TeamRole.OWNER)
    session.add(membership)
    await session.commit()
    await session.refresh(team, attribute_names=["memberships"])
    return _team_payload(team, membership)


@router.patch("/{team_id}")
async def update_team(
    team_id: str,
    payload: TeamRoleUpdate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    team, membership = await _membership(session, team_id, principal.user.id)
    _require_owner(membership)
    team.default_member_role = payload.default_member_role
    await session.commit()
    await session.refresh(team, attribute_names=["memberships"])
    return _team_payload(team, membership)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    payload: TeamDeleteConfirm,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Explicit confirmation is required")
    team, membership = await _membership(session, team_id, principal.user.id)
    _require_owner(membership)
    computers = await session.scalars(select(Computer).where(Computer.owner_team_id == team.id))
    if list(computers):
        raise HTTPException(status_code=409, detail="Transfer or remove team computers before deleting the team")
    await session.delete(team)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{team_id}/invites", status_code=status.HTTP_201_CREATED)
async def create_invite(
    team_id: str,
    payload: InviteCreate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    _, membership = await _membership(session, team_id, principal.user.id)
    _require_owner(membership)
    invited = await session.scalar(select(User).where(User.username == payload.username))
    if invited is None or invited.disabled:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await session.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == invited.id))
    if existing:
        raise HTTPException(status_code=409, detail="User is already a team member")
    token = secrets.token_urlsafe(32)
    invite = TeamInvite(
        team_id=team_id,
        invited_by_user_id=principal.user.id,
        username=invited.username,
        token_hash=token_digest(token),
        expires_at=utc_now() + INVITE_LIFETIME,
    )
    session.add(invite)
    await session.commit()
    return {"id": invite.id, "team_id": team_id, "username": invite.username, "expires_at": invite.expires_at.isoformat(), "invite_token": token}


@router.get("/invites")
async def list_my_invites(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    invites = await session.scalars(
        select(TeamInvite).where(
            TeamInvite.username == principal.user.username,
            TeamInvite.accepted_at.is_(None),
            TeamInvite.expires_at > utc_now(),
        )
    )
    result = []
    for invite in invites:
        team = await session.get(Team, invite.team_id)
        if team:
            result.append({"id": invite.id, "team_id": team.id, "team_name": team.name, "expires_at": invite.expires_at.isoformat()})
    return result


@router.post("/invites/{invite_token}/accept", status_code=status.HTTP_201_CREATED)
async def accept_invite(
    invite_token: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    invite = await session.scalar(
        select(TeamInvite).where(
            or_(TeamInvite.id == invite_token, TeamInvite.token_hash == token_digest(invite_token)),
            TeamInvite.accepted_at.is_(None),
            TeamInvite.expires_at > utc_now(),
        )
    )
    if invite is None or invite.username != principal.user.username:
        raise HTTPException(status_code=404, detail="Invitation not found")
    membership = TeamMember(team_id=invite.team_id, user_id=principal.user.id, role=TeamRole.MEMBER)
    invite.accepted_at = utc_now()
    session.add(membership)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Invitation was already accepted") from None
    team = await session.get(Team, invite.team_id)
    await session.refresh(team, attribute_names=["memberships"])
    return _team_payload(team, membership)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: str,
    user_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    _, actor = await _membership(session, team_id, principal.user.id)
    if user_id == principal.user.id:
        target = actor
    else:
        _require_owner(actor)
        target = await session.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id))
        if target is None:
            raise HTTPException(status_code=404, detail="Team member not found")
    if target.role == TeamRole.OWNER:
        owner_count = await session.scalar(
            select(func.count()).select_from(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.role == TeamRole.OWNER
            )
        )
        if owner_count < 2:
            raise HTTPException(status_code=409, detail="Transfer ownership before removing the last owner")
    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{team_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_by_body(
    team_id: str,
    payload: MemberRemove,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    return await remove_member(team_id, payload.user_id, principal, session)


@router.post("/{team_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_team(
    team_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    _, membership = await _membership(session, team_id, principal.user.id)
    if membership.role == TeamRole.OWNER:
        others = await session.scalar(select(TeamMember.id).where(TeamMember.team_id == team_id, TeamMember.role == TeamRole.OWNER, TeamMember.user_id != principal.user.id).limit(1))
        if others is None:
            raise HTTPException(status_code=409, detail="Transfer ownership before leaving as the last owner")
    await session.delete(membership)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{team_id}/transfer-ownership")
async def transfer_ownership(
    team_id: str,
    payload: TransferRequest,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    _, current = await _membership(session, team_id, principal.user.id)
    _require_owner(current)
    target = await session.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == payload.user_id))
    if target is None or target.id == current.id:
        raise HTTPException(status_code=404, detail="Team member not found")
    current.role = TeamRole.MEMBER
    target.role = TeamRole.OWNER
    await session.commit()
    return {"team_id": team_id, "owner_user_id": target.user_id}


@router.post("/{team_id}/computers/{computer_id}/transfer")
async def transfer_personal_computer_to_team(
    team_id: str,
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    team, membership = await _membership(session, team_id, principal.user.id)
    computer = await session.get(Computer, computer_id)
    if computer is None or computer.owner_user_id != principal.user.id or computer.owner_team_id is not None:
        raise HTTPException(status_code=404, detail="Computer not found")
    if computer.status.value == "online":
        raise HTTPException(status_code=409, detail="Computer must be offline before ownership transfer")
    computer.owner_user_id = None
    computer.owner_team_id = team.id
    await session.commit()
    return {"id": computer.id, "owner_team_id": team.id}
