from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.db.models import ApiToken, User, utc_now
from aicontrol.db.session import get_session

SESSION_COOKIE = "aic_session"
CSRF_COOKIE = "aic_csrf"
SESSION_LABEL_PREFIX = "web-session:"
API_TOKEN_LABEL_PREFIX = "aic-token:"
SESSION_LIFETIME = timedelta(hours=12)
API_TOKEN_SCOPES = {"computers:read", "computers:exec", "scripts:rw", "ai:use", "admin"}


@dataclass(frozen=True)
class SessionPrincipal:
    user: User
    session: ApiToken
    is_api_token: bool = False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _user_response(user: User) -> dict[str, str]:
    return {"id": user.id, "username": user.username, "role": user.role.value}


async def create_browser_session(
    user: User,
    session: AsyncSession,
) -> tuple[str, str]:
    session_token = new_session_token()
    csrf_token = new_csrf_token()
    session.add(
        ApiToken(
            user_id=user.id,
            token_hash=token_digest(session_token),
            label=SESSION_LABEL_PREFIX + token_digest(csrf_token),
            expires_at=utc_now() + SESSION_LIFETIME,
        )
    )
    await session.commit()
    return session_token, csrf_token


async def lookup_session(token: str | None, session: AsyncSession) -> SessionPrincipal | None:
    if not token or len(token) > 128:
        return None
    record = await session.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == token_digest(token),
            ApiToken.label.like(f"{SESSION_LABEL_PREFIX}%"),
            ApiToken.expires_at > utc_now(),
        )
    )
    if record is None:
        return None
    user = await session.get(User, record.user_id)
    if user is None or user.disabled:
        return None
    record.last_used_at = utc_now()
    await session.commit()
    return SessionPrincipal(user, record)


async def lookup_api_token(
    token: str | None, session: AsyncSession, *, remote_ip: str | None = None
) -> SessionPrincipal | None:
    if not token or not token.startswith("aic_") or len(token) > 128:
        return None
    record = await session.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == token_digest(token),
            ApiToken.label.like(f"{API_TOKEN_LABEL_PREFIX}%"),
            (ApiToken.expires_at.is_(None)) | (ApiToken.expires_at > utc_now()),
        )
    )
    if record is None:
        return None
    user = await session.get(User, record.user_id)
    if user is None or user.disabled:
        return None
    record.last_used_at = utc_now()
    record.last_used_ip = remote_ip
    await session.commit()
    return SessionPrincipal(user, record, is_api_token=True)


async def current_session(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SessionPrincipal:
    authorization = request.headers.get("authorization", "")
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not credential or " " in credential:
            raise HTTPException(status_code=401, detail="Authentication required")
        remote_ip = request.client.host if request.client else None
        principal = await lookup_api_token(credential, session, remote_ip=remote_ip)
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        request.state.principal = principal
        return principal
    principal = await lookup_session(request.cookies.get(SESSION_COOKIE), session)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_api_access(scope: str):
    async def dependency(
        request: Request,
        principal: Annotated[SessionPrincipal, Depends(current_session)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> SessionPrincipal:
        return await authorize_api_request(
            request,
            principal,
            session,
            scope=scope,
            computer_id=request.path_params.get("computer_id"),
        )

    return dependency


async def current_user(principal: Annotated[SessionPrincipal, Depends(current_session)]) -> User:
    return principal.user


async def require_csrf(
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(current_session)],
) -> SessionPrincipal:
    if principal.is_api_token:
        raise HTTPException(status_code=403, detail="Browser session required")
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("x-csrf-token")
    stored_digest = principal.session.label.removeprefix(SESSION_LABEL_PREFIX)
    if (
        not csrf_cookie
        or not csrf_header
        or not secrets.compare_digest(csrf_cookie, csrf_header)
        or not secrets.compare_digest(token_digest(csrf_cookie), stored_digest)
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    return principal


async def authorize_api_request(
    request: Request,
    principal: SessionPrincipal,
    session: AsyncSession,
    *,
    scope: str,
    computer_id: str | None = None,
) -> SessionPrincipal:
    if not principal.is_api_token:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf_cookie = request.cookies.get(CSRF_COOKIE)
            csrf_header = request.headers.get("x-csrf-token")
            stored_digest = principal.session.label.removeprefix(SESSION_LABEL_PREFIX)
            if (
                not csrf_cookie
                or not csrf_header
                or not secrets.compare_digest(csrf_cookie, csrf_header)
                or not secrets.compare_digest(token_digest(csrf_cookie), stored_digest)
            ):
                raise HTTPException(status_code=403, detail="CSRF validation failed")
        return principal
    granted = set(principal.session.scopes or [])
    if scope not in granted:
        raise HTTPException(status_code=403, detail="API token scope is insufficient")
    if scope == "admin" and principal.user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    if computer_id is not None:
        computer_ids = principal.session.computer_ids
        group_ids = principal.session.group_ids
        if computer_ids is not None or group_ids is not None:
            allowed_by_group = False
            if computer_id not in (computer_ids or []):
                if group_ids:
                    from aicontrol.db.models import GroupMember

                    membership = await session.scalar(
                        select(GroupMember.id).where(
                            GroupMember.computer_id == computer_id,
                            GroupMember.group_id.in_(group_ids),
                        ).limit(1)
                    )
                    allowed_by_group = membership is not None
                if not allowed_by_group:
                    raise HTTPException(status_code=403, detail="API token is not scoped to this computer")
        from aicontrol.db.models import Computer
        from aicontrol.permissions import PermissionRole, effective_role

        computer = await session.get(Computer, computer_id)
        if computer is None or await effective_role(principal.user, computer, session) == PermissionRole.NONE:
            raise HTTPException(status_code=403, detail="API token user has no access to this computer")
    return principal


async def authenticate_websocket(websocket: WebSocket, session: AsyncSession) -> User | None:
    origin = websocket.headers.get("origin")
    if not origin:
        return None
    scheme = {"ws": "http", "wss": "https"}.get(websocket.url.scheme)
    expected = urlsplit(f"{scheme}://{websocket.headers.get('host', '')}")
    supplied = urlsplit(origin)
    if (
        scheme is None
        or supplied.scheme != expected.scheme
        or supplied.netloc != expected.netloc
        or supplied.path not in ("", "/")
        or supplied.query
        or supplied.fragment
    ):
        return None
    token = websocket.cookies.get(SESSION_COOKIE)
    principal = await lookup_session(token, session)
    return principal.user if principal else None


def set_auth_cookies(response, session_token: str, csrf_token: str, *, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response, *, secure: bool) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="lax")


def user_payload(user: User) -> dict[str, str]:
    return _user_response(user)


def secure_cookie_request(request: Request) -> bool:
    settings = request.app.state.settings
    return request.url.scheme == "https" or settings.public_url.startswith("https://")