from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import (
    API_TOKEN_LABEL_PREFIX,
    API_TOKEN_SCOPES,
    SessionPrincipal,
    require_csrf,
    token_digest,
)
from aicontrol.db.models import ApiToken, Computer, ControlGroup, UserRole, utc_now
from aicontrol.db.session import get_session

router = APIRouter(prefix="/api/auth/tokens", tags=["api-tokens"])


class CreateTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(min_length=1, max_length=len(API_TOKEN_SCOPES))
    expires_at: datetime | None = None
    computer_ids: list[str] | None = Field(default=None, max_length=100)
    group_ids: list[str] | None = Field(default=None, max_length=100)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Token label cannot be blank")
        return normalized

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or not set(value) <= API_TOKEN_SCOPES:
            raise ValueError("Token contains duplicate or unsupported scopes")
        return value

    @field_validator("computer_ids", "group_ids")
    @classmethod
    def unique_resources(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Resource restrictions must be unique")
        return value


def _payload(record: ApiToken) -> dict[str, object]:
    return {
        "id": record.id,
        "label": record.label.removeprefix(API_TOKEN_LABEL_PREFIX),
        "prefix": record.token_prefix,
        "scopes": record.scopes or [],
        "computer_ids": record.computer_ids,
        "group_ids": record.group_ids,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "last_used_ip": record.last_used_ip,
        "created_at": record.created_at.isoformat(),
    }


async def _owned_resource_ids(
    session: AsyncSession,
    principal: SessionPrincipal,
    payload: CreateTokenRequest,
) -> None:
    if payload.computer_ids:
        computers = await session.scalars(
            select(Computer.id).where(
                Computer.id.in_(payload.computer_ids),
                Computer.owner_user_id == principal.user.id,
            )
        )
        if set(computers) != set(payload.computer_ids):
            raise HTTPException(status_code=404, detail="One or more computers were not found")
    if payload.group_ids:
        groups = await session.scalars(
            select(ControlGroup.id).where(
                ControlGroup.id.in_(payload.group_ids),
                ControlGroup.owner_user_id == principal.user.id,
            )
        )
        if set(groups) != set(payload.group_ids):
            raise HTTPException(status_code=404, detail="One or more groups were not found")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_token(
    payload: CreateTokenRequest,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if "admin" in payload.scopes and principal.user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators may create admin-scoped tokens")
    if payload.expires_at is not None:
        expiry = payload.expires_at
        if expiry.tzinfo is None:
            raise HTTPException(status_code=422, detail="Token expiry must include a timezone")
        if expiry.astimezone(UTC) <= utc_now():
            raise HTTPException(status_code=422, detail="Token expiry must be in the future")
    await _owned_resource_ids(session, principal, payload)
    plaintext = "aic_" + secrets.token_urlsafe(32)
    record = ApiToken(
        user_id=principal.user.id,
        token_hash=token_digest(plaintext),
        label=API_TOKEN_LABEL_PREFIX + payload.label,
        token_prefix=plaintext[:12],
        scopes=payload.scopes,
        computer_ids=payload.computer_ids,
        group_ids=payload.group_ids,
        expires_at=payload.expires_at.astimezone(UTC) if payload.expires_at else None,
    )
    session.add(record)
    await session.commit()
    return {**_payload(record), "token": plaintext}


@router.get("")
async def list_tokens(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    records = await session.scalars(
        select(ApiToken)
        .where(
            ApiToken.user_id == principal.user.id,
            ApiToken.label.like(f"{API_TOKEN_LABEL_PREFIX}%"),
        )
        .order_by(ApiToken.created_at.desc())
    )
    return [_payload(record) for record in records]


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    record = await session.scalar(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == principal.user.id,
            ApiToken.label.like(f"{API_TOKEN_LABEL_PREFIX}%"),
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="API token not found")
    await session.delete(record)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
