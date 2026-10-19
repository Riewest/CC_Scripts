from datetime import UTC, datetime, timedelta
from secrets import choice
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import SessionPrincipal, current_session, require_csrf
from aicontrol.db.models import Computer, PairingCode, utc_now
from aicontrol.db.security import hash_pairing_code
from aicontrol.db.session import get_session
from aicontrol.pairing.rate_limit import pairing_creation_limiter
from aicontrol.pairing.schemas import (
    CreatePairingCode,
    PairingCodeResponse,
    PairingStatusResponse,
)

router = APIRouter(prefix="/api", tags=["pairing"])
PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_LENGTH = 6
PAIRING_LIFETIME = timedelta(minutes=15)


def _generate_code() -> str:
    return "".join(choice(PAIRING_ALPHABET) for _ in range(PAIRING_LENGTH))


def _public_base_url(request: Request) -> str:
    configured = request.app.state.settings.public_url.strip()
    parsed = urlsplit(configured)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(status_code=500, detail="AIC_PUBLIC_URL must be an HTTP(S) origin")
    return f"{parsed.scheme}://{parsed.netloc}"


def _response(code: PairingCode, plaintext: str, request: Request) -> PairingCodeResponse:
    base_url = _public_base_url(request)
    command = f"wget run {base_url}/install?code={plaintext}"
    return PairingCodeResponse(
        id=code.id,
        code=plaintext,
        expires_at=_iso_utc(code.expires_at),
        command=command,
    )


def _iso_utc(value: datetime) -> str:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat()


async def _insert_code(
    session: AsyncSession,
    *,
    owner_user_id: str | None,
    owner_team_id: str | None,
    target_computer_id: str | None,
    label: str | None,
) -> tuple[PairingCode, str]:
    plaintext = _generate_code()
    pairing = PairingCode(
        code_hash=hash_pairing_code(plaintext),
        owner_user_id=owner_user_id,
        owner_team_id=owner_team_id,
        target_computer_id=target_computer_id,
        label=label,
        expires_at=utc_now() + PAIRING_LIFETIME,
    )
    session.add(pairing)
    await session.commit()
    await session.refresh(pairing)
    return pairing, plaintext


@router.post("/pairing-codes", response_model=PairingCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_pairing_code(
    payload: CreatePairingCode,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PairingCodeResponse:
    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"create:{principal.user.id}:{client_host}"
    if pairing_creation_limiter.limited(limiter_key):
        raise HTTPException(
            status_code=429,
            detail="Too many pairing codes requested; try again later",
            headers={"Retry-After": "900"},
        )
    if payload.owner != "me":
        raise HTTPException(
            status_code=403,
            detail="Team pairing is unavailable until team membership permissions are implemented",
        )
    pairing_creation_limiter.record(limiter_key)
    pairing, plaintext = await _insert_code(
        session,
        owner_user_id=principal.user.id,
        owner_team_id=None,
        target_computer_id=None,
        label=payload.label,
    )
    return _response(pairing, plaintext, request)


@router.post(
    "/computers/{computer_id}/pairing-code",
    response_model=PairingCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_repair_code(
    computer_id: str,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PairingCodeResponse:
    computer = await session.get(Computer, computer_id)
    if computer is None or computer.owner_user_id != principal.user.id:
        raise HTTPException(status_code=404, detail="Computer not found")
    if computer.owner_team_id is not None:
        raise HTTPException(
            status_code=403,
            detail="Team-owned computer re-pairing is unavailable until team permissions are implemented",
        )
    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"create:{principal.user.id}:{client_host}"
    if pairing_creation_limiter.limited(limiter_key):
        raise HTTPException(
            status_code=429,
            detail="Too many pairing codes requested; try again later",
            headers={"Retry-After": "900"},
        )
    pairing_creation_limiter.record(limiter_key)
    pairing, plaintext = await _insert_code(
        session,
        owner_user_id=None,
        owner_team_id=None,
        target_computer_id=computer.id,
        label=None,
    )
    return _response(pairing, plaintext, request)


@router.get("/pairing-codes/{pairing_id}", response_model=PairingStatusResponse)
async def pairing_status(
    pairing_id: str,
    principal: Annotated[SessionPrincipal, Depends(current_session)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PairingStatusResponse:
    pairing = await session.get(PairingCode, pairing_id)
    if pairing is None:
        raise HTTPException(status_code=404, detail="Pairing request not found")
    if principal.is_api_token:
        raise HTTPException(status_code=403, detail="Browser session required")
    if pairing.owner_user_id != principal.user.id:
        if pairing.target_computer_id is None:
            raise HTTPException(status_code=404, detail="Pairing request not found")
        computer = await session.get(Computer, pairing.target_computer_id)
        if computer is None or computer.owner_user_id != principal.user.id:
            raise HTTPException(status_code=404, detail="Pairing request not found")
    computer = (
        await session.get(Computer, pairing.paired_computer_id)
        if pairing.paired_computer_id
        else None
    )
    paired = None
    if computer is not None:
        paired = {
            "id": computer.id,
            "label": computer.label,
            "kind": str(computer.kind),
            "status": str(computer.status),
        }
    return PairingStatusResponse(
        id=pairing.id,
        expires_at=_iso_utc(pairing.expires_at),
        used=pairing.used_at is not None,
        paired_computer=paired,
    )
