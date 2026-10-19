from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import SessionPrincipal, current_user, require_csrf
from aicontrol.db.models import ApiToken, User, UserRole
from aicontrol.db.session import get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: UserRole | None = None
    disabled: bool | None = None


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


@router.get("/users")
async def list_users(
    _: Annotated[User, Depends(admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    users = await session.scalars(select(User).order_by(User.username))
    return [
        {
            "id": user.id,
            "username": user.username,
            "role": user.role.value,
            "disabled": user.disabled,
            "created_at": user.created_at.isoformat(),
        }
        for user in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    _: Annotated[User, Depends(admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_fields_set
    new_role = payload.role if "role" in changes else target.role
    new_disabled = payload.disabled if "disabled" in changes else target.disabled
    if target.id == principal.user.id and (new_role != UserRole.ADMIN or new_disabled):
        raise HTTPException(status_code=409, detail="Administrators cannot demote or disable themselves")
    if target.role == UserRole.ADMIN and not target.disabled and (
        new_role != UserRole.ADMIN or new_disabled
    ):
        remaining = await session.scalar(
            select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN,
                User.disabled.is_(False),
                User.id != target.id,
            )
        )
        if not remaining:
            raise HTTPException(status_code=409, detail="Cannot disable or demote the last active administrator")
    if "role" in changes and new_role is not None:
        target.role = new_role
    if "disabled" in changes and new_disabled is not None:
        target.disabled = new_disabled
    if target.disabled:
        records = await session.scalars(select(ApiToken).where(ApiToken.user_id == target.id))
        for record in records:
            await session.delete(record)
    await session.commit()
    return {
        "id": target.id,
        "username": target.username,
        "role": target.role.value,
        "disabled": target.disabled,
    }
