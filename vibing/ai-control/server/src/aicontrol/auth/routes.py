from __future__ import annotations

import asyncio
import secrets
from typing import Annotated

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.audit import record
from aicontrol.auth.rate_limit import login_rate_limiter
from aicontrol.auth.schemas import ChangePassword, Credentials
from aicontrol.auth.sessions import (
    SESSION_LABEL_PREFIX,
    SessionPrincipal,
    clear_auth_cookies,
    create_browser_session,
    current_user,
    require_csrf,
    secure_cookie_request,
    set_auth_cookies,
    user_payload,
)
from aicontrol.config import Settings
from aicontrol.db.models import ApiToken, User, UserRole
from aicontrol.db.security import hash_secret, verify_secret
from aicontrol.db.session import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])
DUMMY_PASSWORD_HASH = PasswordHasher().hash(secrets.token_urlsafe(32))
_setup_lock = asyncio.Lock()


def _password_is_valid(password: str) -> bool:
    return len(password) >= 12


def _authenticated_response(
    request: Request,
    user: User,
    session_token: str,
    csrf_token: str,
    response_status: int = status.HTTP_200_OK,
) -> JSONResponse:
    response = JSONResponse(user_payload(user), status_code=response_status)
    set_auth_cookies(
        response,
        session_token,
        csrf_token,
        secure=secure_cookie_request(request),
    )
    return response


@router.get("/setup-state")
async def setup_state(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    local_account_count = await session.scalar(
        select(func.count()).select_from(User).where(User.password_hash.is_not(None))
    )
    settings: Settings = request.app.state.settings
    return {"setup_required": local_account_count == 0, "signup_allowed": settings.allow_signup}


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def setup_admin(
    credentials: Credentials,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    if not _password_is_valid(credentials.password):
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters")

    async with _setup_lock:
        local_account_count = await session.scalar(
            select(func.count()).select_from(User).where(User.password_hash.is_not(None))
        )
        if local_account_count:
            raise HTTPException(status_code=409, detail="Initial setup has already been completed")

        password_hash = await asyncio.to_thread(hash_secret, credentials.password)
        existing_user = await session.scalar(
            select(User).where(User.username == credentials.username)
        )
        if existing_user is not None:
            if existing_user.password_hash is not None:
                raise HTTPException(status_code=409, detail="Initial setup has already been completed")
            existing_user.password_hash = password_hash
            existing_user.role = UserRole.ADMIN
            user = existing_user
        else:
            user = User(
                username=credentials.username,
                password_hash=password_hash,
                role=UserRole.ADMIN,
            )
            session.add(user)
        try:
            await session.flush()
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Initial setup has already been completed",
            ) from exc

    session_token, csrf_token = await create_browser_session(user, session)
    await record(session, action="auth.setup", actor_user_id=user.id, target_type="user", target_id=user.id, source_ip=request.client.host if request.client else None)
    return _authenticated_response(request, user, session_token, csrf_token, status.HTTP_201_CREATED)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    credentials: Credentials,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    settings: Settings = request.app.state.settings
    local_account_count = await session.scalar(
        select(func.count()).select_from(User).where(User.password_hash.is_not(None))
    )
    if not local_account_count:
        raise HTTPException(status_code=409, detail="Complete initial setup first")
    if not settings.allow_signup:
        raise HTTPException(status_code=403, detail="Sign-up is disabled")
    if not _password_is_valid(credentials.password):
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters")
    user = User(
        username=credentials.username,
        password_hash=await asyncio.to_thread(hash_secret, credentials.password),
        role=UserRole.USER,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username is unavailable") from exc
    session_token, csrf_token = await create_browser_session(user, session)
    await record(session, action="auth.register", actor_user_id=user.id, target_type="user", target_id=user.id, source_ip=request.client.host if request.client else None)
    return _authenticated_response(request, user, session_token, csrf_token, status.HTTP_201_CREATED)


@router.post("/login")
async def login(
    credentials: Credentials,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    client_host = request.client.host if request.client else "unknown"
    limiter_key = client_host
    if login_rate_limiter.is_limited(limiter_key):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts; try again later",
            headers={"Retry-After": "60"},
        )
    user = await session.scalar(select(User).where(User.username == credentials.username))
    password_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    valid_password = await asyncio.to_thread(verify_secret, password_hash, credentials.password)
    if user is None or user.disabled or not valid_password:
        login_rate_limiter.record_failure(limiter_key)
        await record(
            session,
            action="auth.login",
            actor_user_id=user.id if user else None,
            target_type="user",
            target_id=user.id if user else None,
            outcome="failure",
            source_ip=client_host,
            details={"reason": "invalid_credentials"},
            commit=False,
        )
        await session.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    login_rate_limiter.clear_key(limiter_key)
    session_token, csrf_token = await create_browser_session(user, session)
    await record(session, action="auth.login", actor_user_id=user.id, target_type="user", target_id=user.id, source_ip=client_host)
    return _authenticated_response(request, user, session_token, csrf_token)


@router.get("/me")
async def me(user: Annotated[User, Depends(current_user)]) -> dict[str, str]:
    return user_payload(user)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await session.delete(principal.session)
    await session.commit()
    await record(
        session, action="auth.logout", actor_user_id=principal.user.id,
        target_type="user", target_id=principal.user.id,
        source_ip=request.client.host if request.client else None,
    )
    clear_auth_cookies(response, secure=secure_cookie_request(request))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/change-password")
async def change_password(
    credentials: ChangePassword,
    request: Request,
    response: Response,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    is_valid = await asyncio.to_thread(
        verify_secret,
        principal.user.password_hash or DUMMY_PASSWORD_HASH,
        credentials.current_password,
    )
    if not is_valid:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if not _password_is_valid(credentials.new_password):
        raise HTTPException(status_code=422, detail="Password must be between 12 and 1024 characters")
    principal.user.password_hash = await asyncio.to_thread(hash_secret, credentials.new_password)
    sessions = await session.scalars(
        select(ApiToken).where(
            ApiToken.user_id == principal.user.id,
            ApiToken.label.like(f"{SESSION_LABEL_PREFIX}%"),
        )
    )
    for browser_session in sessions:
        await session.delete(browser_session)
    await session.commit()
    await record(
        session, action="auth.password_change", actor_user_id=principal.user.id,
        target_type="user", target_id=principal.user.id,
        source_ip=request.client.host if request.client else None,
    )
    clear_auth_cookies(response, secure=secure_cookie_request(request))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
