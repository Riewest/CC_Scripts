from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import SessionPrincipal, require_csrf
from aicontrol.db.models import (
    Computer,
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
from aicontrol.permissions import accessible_computers, can_own, effective_role

router = APIRouter(tags=["groups-sharing"])


class GroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    team_id: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Group name cannot be blank")
        return normalized


class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Group name cannot be blank")
        return normalized


class GroupComputer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    computer_id: str


class ShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_user_id: str | None = None
    subject_team_id: str | None = None
    computer_id: str | None = None
    group_id: str | None = None
    role: ShareRole

    @model_validator(mode="after")
    def validate_subject_target(self) -> ShareCreate:
        if (self.subject_user_id is None) == (self.subject_team_id is None):
            raise ValueError("Specify exactly one user or team recipient")
        if (self.computer_id is None) == (self.group_id is None):
            raise ValueError("Specify exactly one computer or group target")
        return self


async def _group_owner(
    session: AsyncSession,
    group_id: str,
    user: User,
) -> ControlGroup:
    group = await session.get(ControlGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_user_id == user.id:
        return group
    if group.owner_team_id:
        membership = await session.scalar(
            select(TeamMember).where(
                TeamMember.team_id == group.owner_team_id,
                TeamMember.user_id == user.id,
                TeamMember.role == TeamRole.OWNER,
            )
        )
        if membership:
            return group
    user_team_ids = select(TeamMember.team_id).where(TeamMember.user_id == user.id)
    owner_grant = await session.scalar(
        select(Share.id).where(
            Share.group_id == group.id,
            Share.role == ShareRole.OWNER,
            (Share.subject_user_id == user.id) | Share.subject_team_id.in_(user_team_ids),
        ).limit(1)
    )
    if owner_grant is not None:
        return group
    raise HTTPException(status_code=404, detail="Group not found")


async def _can_manage_group(group: ControlGroup, user: User, session: AsyncSession) -> bool:
    if group.owner_user_id == user.id:
        return True
    if group.owner_team_id:
        membership = await session.scalar(
            select(TeamMember.id).where(
                TeamMember.team_id == group.owner_team_id,
                TeamMember.user_id == user.id,
                TeamMember.role == TeamRole.OWNER,
            )
        )
        return membership is not None
    user_team_ids = select(TeamMember.team_id).where(TeamMember.user_id == user.id)
    owner_share = await session.scalar(
        select(Share.id).where(
            Share.group_id == group.id,
            Share.role == ShareRole.OWNER,
            (Share.subject_user_id == user.id) | Share.subject_team_id.in_(user_team_ids),
        ).limit(1)
    )
    return owner_share is not None


async def _may_revoke_group_share(
    share: Share, group: ControlGroup, user: User, session: AsyncSession
) -> bool:
    if share.role == ShareRole.OWNER:
        direct_owner = share.subject_user_id == user.id
        team_owner = False
        if share.subject_team_id:
            team_owner = await session.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == share.subject_team_id,
                    TeamMember.user_id == user.id,
                ).limit(1)
            ) is not None
        return direct_owner or team_owner or await _can_manage_group(group, user, session)
    return await _can_manage_group(group, user, session)


async def _can_share_computer(computer_id: str, user: User, session: AsyncSession) -> Computer:
    computer = await session.get(Computer, computer_id)
    if computer is None:
        raise HTTPException(status_code=404, detail="Computer not found")
    if not can_own(await effective_role(user, computer, session)):
        raise HTTPException(status_code=404, detail="Computer not found")
    return computer


def _group_payload(group: ControlGroup, computer_ids: list[str]) -> dict[str, object]:
    return {
        "id": group.id,
        "name": group.name,
        "owner_user_id": group.owner_user_id,
        "owner_team_id": group.owner_team_id,
        "computer_ids": computer_ids,
        "created_at": group.created_at.isoformat(),
    }


def _share_payload(share: Share) -> dict[str, object]:
    return {
        "id": share.id,
        "subject_user_id": share.subject_user_id,
        "subject_team_id": share.subject_team_id,
        "computer_id": share.computer_id,
        "group_id": share.group_id,
        "role": ShareRole(share.role).value,
        "created_at": share.created_at.isoformat(),
    }


@router.get("/api/groups")
async def list_groups(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    team_ids = select(TeamMember.team_id).where(TeamMember.user_id == principal.user.id)
    group_ids = select(Share.group_id).where(
        (Share.subject_user_id == principal.user.id)
        | Share.subject_team_id.in_(team_ids),
        Share.group_id.is_not(None),
    )
    groups = await session.scalars(
        select(ControlGroup).where(
            (ControlGroup.owner_user_id == principal.user.id)
            | ControlGroup.owner_team_id.in_(team_ids)
            | ControlGroup.id.in_(group_ids)
        ).order_by(ControlGroup.name)
    )
    result = []
    for group in groups:
        computer_ids = await session.scalars(
            select(GroupMember.computer_id).where(GroupMember.group_id == group.id)
        )
        result.append(_group_payload(group, list(computer_ids)))
    return result


@router.post("/api/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    owner_team_id = None
    owner_user_id = principal.user.id
    if payload.team_id:
        membership = await session.scalar(
            select(TeamMember).where(
                TeamMember.team_id == payload.team_id,
                TeamMember.user_id == principal.user.id,
                TeamMember.role == TeamRole.OWNER,
            )
        )
        if membership is None or await session.get(Team, payload.team_id) is None:
            raise HTTPException(status_code=404, detail="Team not found")
        owner_user_id = None
        owner_team_id = payload.team_id
    group = ControlGroup(name=payload.name, owner_user_id=owner_user_id, owner_team_id=owner_team_id)
    session.add(group)
    await session.commit()
    return _group_payload(group, [])


@router.patch("/api/groups/{group_id}")
async def update_group(
    group_id: str,
    payload: GroupUpdate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    group = await _group_owner(session, group_id, principal.user)
    group.name = payload.name
    await session.commit()
    computer_ids = await session.scalars(select(GroupMember.computer_id).where(GroupMember.group_id == group.id))
    return _group_payload(group, list(computer_ids))


@router.delete("/api/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    group = await _group_owner(session, group_id, principal.user)
    await session.delete(group)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/groups/{group_id}/computers", status_code=status.HTTP_201_CREATED)
async def add_group_computer(
    group_id: str,
    payload: GroupComputer,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    group = await _group_owner(session, group_id, principal.user)
    computer = await _can_share_computer(payload.computer_id, principal.user, session)
    if group.owner_team_id and computer.owner_team_id not in {None, group.owner_team_id}:
        raise HTTPException(status_code=409, detail="Computer ownership is incompatible with this team group")
    if group.owner_user_id and computer.owner_team_id is not None:
        raise HTTPException(status_code=409, detail="Team computers cannot be added to a personal group")
    member = GroupMember(group_id=group.id, computer_id=computer.id)
    session.add(member)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Computer is already in this group") from None
    return {"group_id": group.id, "computer_id": computer.id}


@router.delete("/api/groups/{group_id}/computers/{computer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_computer(
    group_id: str,
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await _group_owner(session, group_id, principal.user)
    member = await session.scalar(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.computer_id == computer_id)
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Group computer not found")
    await session.delete(member)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/shares")
async def list_shares(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    owned_computer_ids = select(Computer.id).where(
        Computer.owner_user_id == principal.user.id
    )
    owned_group_ids = select(ControlGroup.id).where(ControlGroup.owner_user_id == principal.user.id)
    owned_team_ids = select(TeamMember.team_id).where(
        TeamMember.user_id == principal.user.id, TeamMember.role == TeamRole.OWNER
    )
    shares = await session.scalars(
        select(Share).where(
            (Share.subject_user_id == principal.user.id)
            | (Share.subject_team_id.in_(select(TeamMember.team_id).where(TeamMember.user_id == principal.user.id)))
            | Share.computer_id.in_(owned_computer_ids)
            | Share.group_id.in_(owned_group_ids)
            | (Share.computer_id.in_(select(Computer.id).where(Computer.owner_team_id.in_(owned_team_ids))))
            | (Share.group_id.in_(select(ControlGroup.id).where(ControlGroup.owner_team_id.in_(owned_team_ids))))
        ).order_by(Share.created_at.desc())
    )
    return [_share_payload(share) for share in shares]


@router.post("/api/shares", status_code=status.HTTP_201_CREATED)
async def create_share(
    payload: ShareCreate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if payload.subject_user_id:
        subject = await session.get(User, payload.subject_user_id)
        if subject is None or subject.disabled:
            raise HTTPException(status_code=404, detail="Share recipient not found")
    if payload.subject_team_id and await session.get(Team, payload.subject_team_id) is None:
        raise HTTPException(status_code=404, detail="Share recipient not found")
    if payload.computer_id:
        computer = await _can_share_computer(payload.computer_id, principal.user, session)
    else:
        computer = None
    if payload.group_id:
        group = await session.get(ControlGroup, payload.group_id)
        if group is None or not await _can_manage_group(group, principal.user, session):
            raise HTTPException(status_code=404, detail="Group not found")
        if group.owner_user_id and payload.subject_user_id == group.owner_user_id:
            raise HTTPException(status_code=409, detail="Cannot share a group back to its owner")
        if group.owner_team_id and payload.subject_team_id == group.owner_team_id:
            raise HTTPException(status_code=409, detail="Team groups are already available to their team")
        if group.owner_team_id and payload.subject_user_id:
            recipient_membership = await session.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == group.owner_team_id,
                    TeamMember.user_id == payload.subject_user_id,
                ).limit(1)
            )
            if recipient_membership is not None:
                raise HTTPException(status_code=409, detail="Team groups are already available to their members")
        if payload.role == ShareRole.OWNER and not await _group_owner(session, group.id, principal.user):
            raise HTTPException(status_code=403, detail="Only a group owner may grant owner access")
        if payload.subject_team_id and group.owner_team_id and payload.subject_team_id != group.owner_team_id:
            raise HTTPException(status_code=409, detail="Team groups can only be shared with their owning team")
    if computer is not None:
        recipient_team_ids = set(
            await session.scalars(
                select(TeamMember.team_id).where(TeamMember.user_id == payload.subject_user_id)
            )
        ) if payload.subject_user_id else set()
        if payload.subject_user_id == principal.user.id or payload.subject_team_id in recipient_team_ids:
            raise HTTPException(status_code=409, detail="Cannot share a computer back to its owner")
        if computer.owner_team_id and payload.subject_team_id == computer.owner_team_id:
            raise HTTPException(status_code=409, detail="Team computers are already available to their team")
        if computer.owner_team_id and payload.subject_user_id:
            recipient_is_member = await session.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == computer.owner_team_id,
                    TeamMember.user_id == payload.subject_user_id,
                ).limit(1)
            )
            if recipient_is_member:
                raise HTTPException(status_code=409, detail="Team computers are already available to their members")
    share = Share(
        subject_user_id=payload.subject_user_id,
        subject_team_id=payload.subject_team_id,
        computer_id=payload.computer_id,
        group_id=payload.group_id,
        role=payload.role,
    )
    session.add(share)
    await session.commit()
    return _share_payload(share)


@router.delete("/api/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    share = await session.get(Share, share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")
    if share.computer_id:
        computer = await session.get(Computer, share.computer_id)
        if computer is None or not can_own(await effective_role(principal.user, computer, session)):
            raise HTTPException(status_code=404, detail="Share not found")
        if share.role == ShareRole.OWNER:
            is_origin_owner = computer.owner_user_id == principal.user.id
            if share.subject_team_id:
                membership = await session.scalar(
                    select(TeamMember.id).where(
                        TeamMember.team_id == computer.owner_team_id,
                        TeamMember.user_id == principal.user.id,
                    ).limit(1)
                )
                is_origin_owner = membership is not None
            if not is_origin_owner:
                raise HTTPException(status_code=404, detail="Share not found")
    if share.group_id:
        group = await session.get(ControlGroup, share.group_id)
        if group is None or not await _may_revoke_group_share(share, group, principal.user, session):
            raise HTTPException(status_code=404, detail="Share not found")
        if share.role == ShareRole.OWNER and not (
            group.owner_user_id == principal.user.id
            or (
                group.owner_team_id is not None
                and await session.scalar(
                    select(TeamMember.id).where(
                        TeamMember.team_id == group.owner_team_id,
                        TeamMember.user_id == principal.user.id,
                    ).limit(1)
                ) is not None
            )
        ):
            raise HTTPException(status_code=404, detail="Share not found")
    await session.delete(share)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/sharing/computers")
async def list_accessible_computers(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    return [
        {
            "id": computer.id,
            "label": computer.label,
            "role": role.name.lower(),
            "owner_team_id": computer.owner_team_id,
            "kind": str(computer.kind),
            "status": str(computer.status),
        }
        for computer, role in await accessible_computers(principal.user, session)
    ]


@router.get("/api/sharing/recipients")
async def list_share_recipients(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, list[dict[str, str]]]:
    users = await session.scalars(
        select(User).where(User.id != principal.user.id, User.disabled.is_(False)).order_by(User.username)
    )
    team_ids = select(TeamMember.team_id).where(TeamMember.user_id == principal.user.id)
    teams = await session.scalars(select(Team).where(Team.id.in_(team_ids)).order_by(Team.name))
    return {
        "users": [{"id": user.id, "name": user.username} for user in users],
        "teams": [{"id": team.id, "name": team.name} for team in teams],
    }
