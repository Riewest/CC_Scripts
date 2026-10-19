from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.audit import event_filter_statement, event_payload, export_csv, prune_before
from aicontrol.auth.sessions import SessionPrincipal, require_csrf
from aicontrol.db.models import AuditEvent, UserRole, utc_now
from aicontrol.db.session import get_session

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise HTTPException(status_code=422, detail="Audit timestamps must include a timezone")
    return value.astimezone(UTC)


async def _visible_statement(principal: SessionPrincipal, session: AsyncSession):
    from aicontrol.permissions import PermissionRole, accessible_computers

    if principal.user.role == UserRole.ADMIN:
        return select(AuditEvent)
    accessible = await accessible_computers(principal.user, session)
    owned = [computer.id for computer, role in accessible if role >= PermissionRole.OWNER]
    operated = [computer.id for computer, role in accessible if role >= PermissionRole.OPERATOR]
    visibility = [AuditEvent.actor_user_id == principal.user.id]
    if owned:
        visibility.append(AuditEvent.computer_id.in_(owned))
    if operated:
        visibility.append(
            AuditEvent.computer_id.in_(operated)
            & (AuditEvent.actor_user_id == principal.user.id)
        )
    return select(AuditEvent).where(or_(*visibility))


@router.get("")
async def list_audit_events(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    computer_id: str | None = None,
    action: str | None = Query(default=None, max_length=120),
    actor_user_id: str | None = None,
    actor_token_id: str | None = None,
    actor_type: str | None = Query(default=None, max_length=24),
    outcome: str | None = Query(default=None, max_length=24),
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    start, end = _datetime(start), _datetime(end)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must be before end")
    statement = event_filter_statement(
        user_id=principal.user.id,
        computer_id=computer_id,
        action=action,
        actor_user_id=actor_user_id,
        actor_token_id=actor_token_id,
        actor_type=actor_type,
        outcome=outcome,
        start=start,
        end=end,
    )
    base = await _visible_statement(principal, session)
    statement = statement.where(AuditEvent.id.in_(base.with_only_columns(AuditEvent.id)))
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    page = list(await session.scalars(statement.offset(offset).limit(limit)))
    return {
        "items": [event_payload(event) for event in page],
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": offset + len(page) < total,
    }


@router.get("/export")
async def export_audit_events(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    format: str = Query(default="json", pattern="^(json|csv)$"),
    computer_id: str | None = None,
    action: str | None = Query(default=None, max_length=120),
    actor_user_id: str | None = None,
    actor_token_id: str | None = None,
    actor_type: str | None = Query(default=None, max_length=24),
    outcome: str | None = Query(default=None, max_length=24),
    start: datetime | None = None,
    end: datetime | None = None,
) -> Response:
    start, end = _datetime(start), _datetime(end)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must be before end")
    statement = event_filter_statement(
        user_id=principal.user.id,
        computer_id=computer_id,
        action=action,
        actor_user_id=actor_user_id,
        actor_token_id=actor_token_id,
        actor_type=actor_type,
        outcome=outcome,
        start=start,
        end=end,
    )
    base = await _visible_statement(principal, session)
    statement = statement.where(AuditEvent.id.in_(base.with_only_columns(AuditEvent.id))).limit(10_000)
    events = list(await session.scalars(statement))
    if format == "csv":
        return Response(
            export_csv(events),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="ai-control-audit.csv"'},
        )
    return Response(
        content=json.dumps([event_payload(event) for event in events], ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="ai-control-audit.json"'},
    )


@router.delete("/retention", status_code=status.HTTP_204_NO_CONTENT)
async def prune_audit_events(
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    before: datetime,
) -> Response:
    if principal.user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator access required")
    cutoff = _datetime(before)
    if cutoff is None or cutoff >= utc_now() - timedelta(days=1):
        raise HTTPException(status_code=422, detail="Retention cutoff must be at least one day in the past")
    source_ip = request.client.host if request.client else None
    await prune_before(session, cutoff, actor_user_id=principal.user.id, source_ip=source_ip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
