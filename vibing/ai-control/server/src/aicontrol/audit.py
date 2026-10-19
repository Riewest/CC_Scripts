from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.db.models import AuditEvent, Computer, new_id, utc_now

_SECRET_KEYS = re.compile(
    r"(secret|password|token|api[_-]?key|authorization|credential|cookie|csrf|code_verifier|nonce)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_AIC_TOKEN = re.compile(r"\baic_[A-Za-z0-9_-]{12,}\b")
_KEY_VALUE_SECRET = re.compile(
    r"(?i)\b(password|secret|api[_-]?key|token|authorization|cookie|csrf)\b\s*[:=]\s*(?:['\"]([^'\"]*)['\"]|([^\s,;]+))"
)
_REDACTED = "[REDACTED]"


def _contains_formula(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith(("=", "+", "-", "@", "\t", "\r"))
    if isinstance(value, Mapping):
        return any(_contains_formula(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_formula(item) for item in value)
    return False


def redact_text(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _AIC_TOKEN.sub(_REDACTED, value)
    return _KEY_VALUE_SECRET.sub(lambda match: f"{match.group(1)}={_REDACTED}", value)


def redact(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        return "[TRUNCATED]"
    if isinstance(value, str):
        return redact_text(value[:20_000])
    if isinstance(value, Mapping):
        return {
            str(key)[:200]: _REDACTED if _SECRET_KEYS.search(str(key)) else redact(item, depth=depth + 1)
            for key, item in list(value.items())[:500]
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item, depth=depth + 1) for item in list(value)[:500]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2000]


def _clean_ip(source_ip: str | None) -> str | None:
    if not source_ip:
        return None
    return source_ip[:64]


async def record(
    session: AsyncSession,
    *,
    action: str,
    actor_user_id: str | None = None,
    actor_token_id: str | None = None,
    actor_type: str | None = None,
    computer_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str = "success",
    source_ip: str | None = None,
    details: Any = None,
    commit: bool = True,
) -> AuditEvent:
    if actor_type is None:
        actor_type = "token" if actor_token_id else "user" if actor_user_id else "system"
    event = AuditEvent(
        id=new_id(),
        actor_user_id=actor_user_id,
        actor_token_id=actor_token_id,
        actor_type=actor_type[:24],
        computer_id=computer_id,
        action=action[:120],
        target_type=target_type[:80] if target_type else None,
        target_id=target_id[:36] if target_id else None,
        outcome=outcome[:24],
        source_ip=_clean_ip(source_ip),
        details=redact(details) if details is not None else None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(event)
    if commit:
        await session.commit()
    return event


def event_payload(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "created_at": event.created_at.astimezone(UTC).isoformat(),
        "actor_type": event.actor_type,
        "actor_user_id": event.actor_user_id,
        "actor_token_id": event.actor_token_id,
        "computer_id": event.computer_id,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "outcome": event.outcome,
        "source_ip": event.source_ip,
        "details": event.details,
    }


def export_csv(events: list[AuditEvent]) -> str:
    output = io.StringIO(newline="")
    fields = [
        "id", "created_at", "actor_type", "actor_user_id", "actor_token_id", "computer_id",
        "action", "target_type", "target_id", "outcome", "source_ip", "details",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for event in events:
        row = event_payload(event)
        row["details"] = json.dumps(row["details"], ensure_ascii=False, sort_keys=True)
        if _contains_formula(event.details):
            row["details"] = "'" + row["details"]
        writer.writerow(
            {
                key: "'" + value
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                else value
                for key, value in row.items()
            }
        )
    return output.getvalue()


async def record_request(
    request,
    session: AsyncSession,
    *,
    action: str,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: str | None = None,
    computer_id: str | None = None,
    details: Any = None,
    commit: bool = True,
) -> AuditEvent:
    principal = getattr(request.state, "principal", None)
    return await record(
        session,
        action=action,
        actor_user_id=principal.user.id if principal else None,
        actor_token_id=(
            principal.session.id
            if principal is not None and principal.is_api_token
            else None
        ),
        actor_type="token" if principal is not None and principal.is_api_token else None,
        source_ip=request.client.host if request.client else None,
        target_type=target_type,
        target_id=target_id,
        computer_id=computer_id,
        outcome=outcome,
        details=details,
        commit=commit,
    )


async def can_view_event(event: AuditEvent, user_id: str, session: AsyncSession, *, is_admin: bool) -> bool:
    if is_admin:
        return True
    if event.computer_id:
        from aicontrol.db.models import User
        from aicontrol.permissions import PermissionRole, effective_role

        user = await session.get(User, user_id)
        computer = await session.get(Computer, event.computer_id)
        if user is None or computer is None:
            return False
        role = await effective_role(user, computer, session)
        if role >= PermissionRole.OWNER:
            return True
        if role < PermissionRole.OPERATOR:
            return False
        if event.actor_user_id == user_id:
            return True
        if event.actor_token_id:
            from aicontrol.db.models import ApiToken

            token = await session.get(ApiToken, event.actor_token_id)
            return token is not None and token.user_id == user_id
        return False
    return event.actor_user_id == user_id


async def prune_before(
    session: AsyncSession,
    cutoff: datetime,
    *,
    actor_user_id: str,
    source_ip: str | None = None,
) -> int:
    from sqlalchemy import delete, func

    count = await session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.created_at < cutoff)
    )
    await session.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
    await record(
        session,
        action="audit.retention_pruned",
        actor_user_id=actor_user_id,
        source_ip=source_ip,
        details={"deleted_count": count or 0, "before": cutoff.isoformat()},
        commit=True,
    )
    return count or 0


def event_filter_statement(
    *,
    user_id: str,
    computer_id: str | None = None,
    action: str | None = None,
    actor_user_id: str | None = None,
    actor_token_id: str | None = None,
    actor_type: str | None = None,
    outcome: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
):
    statement = select(AuditEvent)
    if computer_id:
        statement = statement.where(AuditEvent.computer_id == computer_id)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if actor_user_id:
        statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
    if actor_token_id:
        statement = statement.where(AuditEvent.actor_token_id == actor_token_id)
    if actor_type:
        statement = statement.where(AuditEvent.actor_type == actor_type)
    if outcome:
        statement = statement.where(AuditEvent.outcome == outcome)
    if start:
        statement = statement.where(AuditEvent.created_at >= start)
    if end:
        statement = statement.where(AuditEvent.created_at <= end)
    return statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
