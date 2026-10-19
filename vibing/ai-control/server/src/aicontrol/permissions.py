from __future__ import annotations

from enum import IntEnum

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.db.models import (
    Computer,
    GroupMember,
    Share,
    ShareRole,
    Team,
    TeamMember,
    TeamRole,
    User,
)


class PermissionRole(IntEnum):
    NONE = 0
    VIEWER = 1
    OPERATOR = 2
    OWNER = 3


def _enum_role(value: ShareRole) -> PermissionRole:
    return {
        ShareRole.VIEWER: PermissionRole.VIEWER,
        ShareRole.OPERATOR: PermissionRole.OPERATOR,
        ShareRole.OWNER: PermissionRole.OWNER,
    }[ShareRole(value)]


def role_at_least(actual: PermissionRole, required: PermissionRole) -> bool:
    return actual >= required


async def effective_role(user: User, computer: Computer, session: AsyncSession) -> PermissionRole:
    if user.disabled:
        return PermissionRole.NONE
    if computer.owner_user_id == user.id:
        return PermissionRole.OWNER
    roles: list[PermissionRole] = []
    if computer.owner_team_id:
        membership = await session.scalar(
            select(TeamMember).where(
                TeamMember.team_id == computer.owner_team_id,
                TeamMember.user_id == user.id,
            )
        )
        if membership:
            if membership.role == TeamRole.OWNER:
                return PermissionRole.OWNER
            team = await session.get(Team, computer.owner_team_id)
            if team:
                roles.append(_enum_role(team.default_member_role))
    user_team_ids = set(
        await session.scalars(select(TeamMember.team_id).where(TeamMember.user_id == user.id))
    )
    group_ids = set(
        await session.scalars(select(GroupMember.group_id).where(GroupMember.computer_id == computer.id))
    )
    targets = [Share.computer_id == computer.id]
    if group_ids:
        targets.append(Share.group_id.in_(group_ids))
    subject_filters = [Share.subject_user_id == user.id]
    if user_team_ids:
        subject_filters.append(Share.subject_team_id.in_(user_team_ids))
    shares = await session.scalars(
        select(Share).where(and_(or_(*targets), or_(*subject_filters)))
    )
    for grant in shares:
        roles.append(_enum_role(grant.role))
    return max(roles, default=PermissionRole.NONE)


def can_operate(role: PermissionRole) -> bool:
    return role_at_least(role, PermissionRole.OPERATOR)


def can_own(role: PermissionRole) -> bool:
    return role_at_least(role, PermissionRole.OWNER)


async def accessible_computers(user: User, session: AsyncSession) -> list[tuple[Computer, PermissionRole]]:
    computers = await session.scalars(select(Computer))
    results: list[tuple[Computer, PermissionRole]] = []
    for computer in computers:
        role = await effective_role(user, computer, session)
        if role != PermissionRole.NONE:
            results.append((computer, role))
    return results


async def require_computer_role(
    user: User,
    computer_id: str,
    session: AsyncSession,
    required: PermissionRole,
) -> tuple[Computer, PermissionRole]:
    computer = await session.get(Computer, computer_id)
    if computer is None:
        raise HTTPException(status_code=404, detail="Computer not found")
    role = await effective_role(user, computer, session)
    if not role_at_least(role, required):
        raise HTTPException(
            status_code=404 if role == PermissionRole.NONE else 403,
            detail="Computer not found" if role == PermissionRole.NONE else "Computer permission denied",
        )
    return computer, role
