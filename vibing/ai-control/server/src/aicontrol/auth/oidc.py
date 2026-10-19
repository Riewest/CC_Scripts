from __future__ import annotations

import base64
import hashlib
import secrets
import time
from datetime import timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import (
    SESSION_COOKIE,
    SessionPrincipal,
    create_browser_session,
    lookup_session,
    require_csrf,
    secure_cookie_request,
    set_auth_cookies,
    token_digest,
)
from aicontrol.config import OidcProviderSettings, Settings
from aicontrol.db.models import OidcFlow, User, UserIdentity, UserRole, utc_now
from aicontrol.db.session import get_session

router = APIRouter(prefix="/api/auth/oidc", tags=["oidc"])
FLOW_COOKIE = "aic_oidc_flow"
FLOW_LIFETIME = timedelta(minutes=10)
ALLOWED_ID_TOKEN_ALGORITHMS = ["RS256", "ES256"]


def _provider(settings: Settings, name: str) -> OidcProviderSettings:
    for configured in settings.oidc_providers:
        if configured.name == name:
            return configured
    raise HTTPException(status_code=404, detail="OIDC provider not found")


def _redirect_uri(request: Request, provider_name: str) -> str:
    settings: Settings = request.app.state.settings
    return f"{settings.public_url.rstrip('/')}/api/auth/oidc/{provider_name}/callback"


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _https_endpoint(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError("OIDC metadata contains a non-HTTPS endpoint")
    return value


async def _get_json(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        value = response.json()
    if not isinstance(value, dict):
        raise ValueError("OIDC endpoint returned an invalid response")
    return value


async def _discover(provider: OidcProviderSettings) -> dict[str, Any]:
    issuer = provider.issuer_url.rstrip("/")
    if not issuer.startswith("https://"):
        raise ValueError("OIDC issuer must use HTTPS")
    metadata = await _get_json(f"{issuer}/.well-known/openid-configuration")
    if metadata.get("issuer", "").rstrip("/") != issuer:
        raise ValueError("OIDC discovery issuer mismatch")
    metadata["authorization_endpoint"] = _https_endpoint(metadata.get("authorization_endpoint"))
    metadata["token_endpoint"] = _https_endpoint(metadata.get("token_endpoint"))
    metadata["jwks_uri"] = _https_endpoint(metadata.get("jwks_uri"))
    return metadata


async def _exchange_code(
    metadata: dict[str, Any], provider: OidcProviderSettings, code: str,
    redirect_uri: str, verifier: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
            auth=(provider.client_id, provider.client_secret.get_secret_value()),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        result = response.json()
    if not isinstance(result, dict):
        raise ValueError("OIDC token endpoint returned an invalid response")
    return result


def _verified_claims(
    encoded_token: str,
    jwks: dict[str, Any],
    provider: OidcProviderSettings,
    nonce: str,
) -> dict[str, Any]:
    decoded = jwt.decode(
        encoded_token,
        KeySet.import_key_set(jwks),
        algorithms=ALLOWED_ID_TOKEN_ALGORITHMS,
    )
    if decoded.header.get("alg") not in ALLOWED_ID_TOKEN_ALGORITHMS:
        raise ValueError("ID token uses an unsupported signing algorithm")
    payload = dict(decoded.claims)
    JWTClaimsRegistry(exp={"essential": True}, iat={"essential": True}, leeway=60).validate(
        payload
    )
    issuer = payload.get("iss")
    if not isinstance(issuer, str) or issuer.rstrip("/") != provider.issuer_url.rstrip("/"):
        raise ValueError("ID token issuer mismatch")
    audience = payload.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if not all(isinstance(value, str) for value in audiences) or provider.client_id not in audiences:
        raise ValueError("ID token audience mismatch")
    if isinstance(audience, list) and len(audience) > 1 and payload.get("azp") != provider.client_id:
        raise ValueError("ID token authorized party mismatch")
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise ValueError("ID token subject is missing")
    if not isinstance(payload.get("exp"), (int, float)) or not isinstance(payload.get("iat"), (int, float)):
        raise ValueError("ID token timestamps are missing")
    if payload["iat"] > time.time() + 60:
        raise ValueError("ID token was issued in the future")
    token_nonce = payload.get("nonce")
    if not isinstance(token_nonce, str) or not secrets.compare_digest(token_nonce, nonce):
        raise ValueError("ID token nonce mismatch")
    return payload


def _domain_allowed(claims: dict[str, Any], provider: OidcProviderSettings) -> bool:
    allowed = {domain.casefold() for domain in provider.allowed_email_domains}
    if not allowed:
        return True
    email = claims.get("email")
    if claims.get("email_verified") is not True or not isinstance(email, str) or "@" not in email:
        return False
    return email.rsplit("@", 1)[1].casefold() in allowed


def _generated_username(provider: OidcProviderSettings, subject: str) -> str:
    provider_part = "".join(character.lower() if character.isalnum() else "-" for character in provider.name)
    subject_part = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:24]
    return f"oidc-{provider_part[:30]}-{subject_part}"[:80]


@router.get("/providers")
async def list_providers(request: Request) -> list[dict[str, str]]:
    settings: Settings = request.app.state.settings
    return [{"name": provider.name} for provider in settings.oidc_providers]


async def _begin_flow(
    request: Request,
    session: AsyncSession,
    provider_name: str,
    link_user_id: str | None,
) -> tuple[str, str]:
    settings: Settings = request.app.state.settings
    provider = _provider(settings, provider_name)
    try:
        metadata = await _discover(provider)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="OIDC provider configuration is unavailable") from None

    state = secrets.token_urlsafe(32)
    browser_token = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    session.add(
        OidcFlow(
            state_hash=token_digest(state),
            browser_hash=token_digest(browser_token),
            provider=provider.name,
            nonce=nonce,
            code_verifier=verifier,
            link_user_id=link_user_id,
            expires_at=utc_now() + FLOW_LIFETIME,
        )
    )
    await session.commit()
    callback = _redirect_uri(request, provider.name)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": callback,
            "scope": " ".join(provider.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return f"{metadata['authorization_endpoint']}?{query}", browser_token


def _set_flow_cookie(response: Response, browser_token: str, request: Request) -> None:
    response.set_cookie(
        FLOW_COOKIE,
        browser_token,
        max_age=int(FLOW_LIFETIME.total_seconds()),
        httponly=True,
        secure=secure_cookie_request(request),
        samesite="lax",
        path="/api/auth/oidc",
    )


@router.get("/{provider_name}/login")
async def start_login(
    provider_name: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RedirectResponse:
    authorization_url, browser_token = await _begin_flow(request, session, provider_name, None)
    response = RedirectResponse(authorization_url, status_code=302)
    _set_flow_cookie(response, browser_token, request)
    return response


@router.post("/{provider_name}/link")
async def start_link(
    provider_name: str,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    authorization_url, browser_token = await _begin_flow(
        request, session, provider_name, principal.user.id
    )
    response = JSONResponse({"authorization_url": authorization_url})
    _set_flow_cookie(response, browser_token, request)
    return response


@router.get("/{provider_name}/callback")
async def callback(
    provider_name: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    state = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    browser_token = request.cookies.get(FLOW_COOKIE, "")
    flow = await session.scalar(
        select(OidcFlow).where(
            OidcFlow.state_hash == token_digest(state),
            OidcFlow.provider == provider_name,
            OidcFlow.expires_at > utc_now(),
        )
    ) if state else None
    if request.query_params.get("error") or not code or flow is None or not browser_token:
        raise HTTPException(status_code=400, detail="OIDC sign-in could not be completed")
    if not secrets.compare_digest(flow.browser_hash, token_digest(browser_token)):
        await session.delete(flow)
        await session.commit()
        raise HTTPException(status_code=400, detail="OIDC sign-in could not be completed")

    await session.delete(flow)
    await session.commit()
    settings: Settings = request.app.state.settings
    provider = _provider(settings, provider_name)
    try:
        metadata = await _discover(provider)
        token_response = await _exchange_code(
            metadata, provider, code, _redirect_uri(request, provider.name), flow.code_verifier
        )
        encoded_token = token_response.get("id_token")
        if not isinstance(encoded_token, str):
            raise ValueError("ID token is missing")
        jwks = await _get_json(metadata["jwks_uri"])
        claims = _verified_claims(encoded_token, jwks, provider, flow.nonce)
        if not _domain_allowed(claims, provider):
            raise ValueError("Email domain is not permitted")
    except (httpx.HTTPError, JoseError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="OIDC sign-in could not be verified") from None

    identity = await session.scalar(
        select(UserIdentity).where(
            UserIdentity.issuer == provider.issuer_url.rstrip("/"),
            UserIdentity.subject == claims["sub"],
        )
    )
    if flow.link_user_id is not None:
        active = await lookup_session(request.cookies.get(SESSION_COOKIE), session)
        if active is None or active.user.id != flow.link_user_id:
            raise HTTPException(status_code=401, detail="Sign in again before linking an identity")
        if identity is not None:
            raise HTTPException(status_code=409, detail="This identity is already linked")
        session.add(
            UserIdentity(
                user_id=flow.link_user_id,
                issuer=provider.issuer_url.rstrip("/"),
                subject=claims["sub"],
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="This identity is already linked") from None
        linked = RedirectResponse("/?identity=linked", status_code=303)
        linked.delete_cookie(FLOW_COOKIE, path="/api/auth/oidc")
        return linked

    if identity is not None:
        user = await session.get(User, identity.user_id)
        if user is None or user.disabled:
            raise HTTPException(status_code=401, detail="OIDC sign-in could not be verified")
    else:
        if not provider.auto_create_users:
            raise HTTPException(status_code=403, detail="Account creation is disabled for this provider")
        user = User(username=_generated_username(provider, claims["sub"]), role=UserRole.USER)
        user.identities.append(
            UserIdentity(issuer=provider.issuer_url.rstrip("/"), subject=claims["sub"])
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            identity = await session.scalar(
                select(UserIdentity).where(
                    UserIdentity.issuer == provider.issuer_url.rstrip("/"),
                    UserIdentity.subject == claims["sub"],
                )
            )
            user = await session.get(User, identity.user_id) if identity else None
            if user is None or user.disabled:
                raise HTTPException(status_code=401, detail="OIDC sign-in could not be verified") from None

    session_token, csrf_token = await create_browser_session(user, session)
    authenticated = RedirectResponse("/", status_code=303)
    set_auth_cookies(
        authenticated,
        session_token,
        csrf_token,
        secure=secure_cookie_request(request),
    )
    authenticated.delete_cookie(FLOW_COOKIE, path="/api/auth/oidc")
    return authenticated


