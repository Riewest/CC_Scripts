from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aicontrol.auth import oidc
from aicontrol.config import OidcProviderSettings, Settings
from aicontrol.db.models import ApiToken, Base, OidcFlow, User, UserIdentity
from aicontrol.db.session import get_session
from aicontrol.main import create_app

ISSUER = "https://issuer.example.test"


@pytest.fixture
def auth_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'oidc.db').as_posix()}"

    async def create_tables() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_tables())
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator:
        async with factory() as session:
            yield session

    app = create_app(Settings(_env_file=None, database_url=database_url, allow_signup=True))
    app.state.test_database_url = database_url
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client
    asyncio.run(engine.dispose())


@pytest.fixture
def oidc_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = RSAKey.import_key(
        private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
        {"kid": "test-key", "use": "sig"},
    )
    public = RSAKey.import_key(
        private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo),
        {"kid": "test-key", "use": "sig"},
    )
    return private, {"keys": [public.as_dict()]}


def _id_token(private, *, nonce: str, subject: str = "subject-1", email: str = "user@example.test", **overrides):
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": "client-id",
        "sub": subject,
        "exp": now + timedelta(minutes=3),
        "iat": now,
        "nonce": nonce,
        "email": email,
        "email_verified": True,
    }
    claims.update(overrides)
    return jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, private, algorithms=["RS256"])


def _provider(*, allowed_domains: list[str] | None = None) -> OidcProviderSettings:
    return OidcProviderSettings(
        name="test-provider",
        issuer_url=ISSUER,
        client_id="client-id",
        client_secret="client-secret",
        allowed_email_domains=allowed_domains or [],
    )


def _mock_discovery(monkeypatch):
    monkeypatch.setattr(oidc, "_discover", lambda _: _async({
        "issuer": ISSUER,
        "authorization_endpoint": "https://issuer.example.test/authorize",
        "token_endpoint": "https://issuer.example.test/token",
        "jwks_uri": "https://issuer.example.test/jwks",
    }))


async def _async(value):
    return value


def _begin(client, provider_name="test-provider"):
    started = client.get(f"/api/auth/oidc/{provider_name}/login", follow_redirects=False)
    assert started.status_code == 302
    authorization = urlparse(started.headers["location"])
    query = parse_qs(authorization.query)
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    state = query["state"][0]
    flow = _read_flow(client, state)
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(flow["code_verifier"].encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    assert query["code_challenge"] == [expected_challenge]
    return state


def _callback(client, state: str, **params):
    return client.get(
        "/api/auth/oidc/test-provider/callback",
        params={"state": state, "code": "one-time-code", **params},
        follow_redirects=False,
    )


def test_oidc_login_verifies_signature_and_creates_stable_user(auth_client, monkeypatch, oidc_keys):
    private, jwks = oidc_keys
    auth_client.app.state.settings.oidc_providers = [_provider()]
    _mock_discovery(monkeypatch)
    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    async def exchange(_metadata, _provider, _code, _redirect, verifier):
        assert len(verifier) >= 43
        return {"id_token": _id_token(private, nonce=flow["nonce"])}
    monkeypatch.setattr(oidc, "_exchange_code", exchange)
    monkeypatch.setattr(oidc, "_get_json", lambda _url: _async(jwks))
    response = _callback(auth_client, state)
    assert response.status_code == 303
    assert auth_client.get("/api/auth/me").status_code == 200
    assert auth_client.get("/api/auth/me").json()["role"] == "user"
    assert auth_client.get("/api/auth/me").json()["username"].startswith("oidc-test-provider-")
    assert auth_client.get("/api/auth/setup-state").json()["setup_required"] is True
    user_id = auth_client.get("/api/auth/me").json()["id"]
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]})
    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    monkeypatch.setattr(
        oidc,
        "_exchange_code",
        lambda *_: _async({"id_token": _id_token(private, nonce=flow["nonce"])}),
    )
    assert _callback(auth_client, state).status_code == 303
    assert auth_client.get("/api/auth/me").json()["id"] == user_id


def test_oidc_state_is_browser_bound_one_use_and_wrong_state_rejected(auth_client, monkeypatch):
    auth_client.app.state.settings.oidc_providers = [_provider()]
    _mock_discovery(monkeypatch)
    monkeypatch.setattr(oidc, "_exchange_code", lambda *_: _async({}))
    state = _begin(auth_client)
    wrong_state = _callback(auth_client, "attacker-state")
    assert wrong_state.status_code == 400
    saved_cookie = auth_client.cookies.get(oidc.FLOW_COOKIE)
    auth_client.cookies.delete(oidc.FLOW_COOKIE, path="/api/auth/oidc")
    assert _callback(auth_client, state).status_code == 400
    auth_client.cookies.set(oidc.FLOW_COOKIE, saved_cookie, path="/api/auth/oidc")
    valid_state = _callback(auth_client, state)
    assert valid_state.status_code == 401
    assert "could not be verified" in valid_state.json()["detail"]
    assert _callback(auth_client, state).status_code == 400


def test_oidc_rejects_bad_nonce_and_signature(auth_client, monkeypatch, oidc_keys):
    private, jwks = oidc_keys
    other_raw_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_private = RSAKey.import_key(
        other_raw_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
        {"kid": "test-key", "use": "sig"},
    )
    auth_client.app.state.settings.oidc_providers = [_provider()]
    _mock_discovery(monkeypatch)
    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    monkeypatch.setattr(oidc, "_exchange_code", lambda *_: _async({"id_token": _id_token(private, nonce="wrong-nonce")}))
    monkeypatch.setattr(oidc, "_get_json", lambda _: _async(jwks))
    assert _callback(auth_client, state).status_code == 401

    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    monkeypatch.setattr(oidc, "_exchange_code", lambda *_: _async({"id_token": _id_token(other_private, nonce=flow["nonce"])}))
    assert _callback(auth_client, state).status_code == 401


def test_oidc_domain_restriction_and_expired_token(auth_client, monkeypatch, oidc_keys):
    private, jwks = oidc_keys
    auth_client.app.state.settings.oidc_providers = [_provider(allowed_domains=["example.test"])]
    _mock_discovery(monkeypatch)
    monkeypatch.setattr(oidc, "_get_json", lambda _: _async(jwks))
    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    monkeypatch.setattr(oidc, "_exchange_code", lambda *_: _async({"id_token": _id_token(private, nonce=flow["nonce"], email="user@outside.test")}))
    assert _callback(auth_client, state).status_code == 401

    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    past = datetime.now(UTC) - timedelta(minutes=2)
    monkeypatch.setattr(oidc, "_exchange_code", lambda *_: _async({"id_token": _id_token(private, nonce=flow["nonce"], exp=past)}))
    assert _callback(auth_client, state).status_code == 401


def _read_flow(client, state):
    async def read():
        engine = create_async_engine(client.app.state.test_database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            result = await session.scalar(select(OidcFlow).where(OidcFlow.state_hash == oidc.token_digest(state)))
            assert result is not None
            result_data = {"nonce": result.nonce, "code_verifier": result.code_verifier}
        await engine.dispose()
        return result_data
    return asyncio.run(read())


def test_oidc_link_requires_logged_in_user_and_never_links_by_email(auth_client, monkeypatch, oidc_keys):
    private, jwks = oidc_keys
    auth_client.app.state.settings.oidc_providers = [_provider()]
    assert auth_client.post("/api/auth/oidc/test-provider/link").status_code == 401
    auth_client.post("/api/auth/setup", json={"username": "owner", "password": "a-very-long-password"})
    csrf = auth_client.cookies["aic_csrf"]
    _mock_discovery(monkeypatch)
    started = auth_client.post("/api/auth/oidc/test-provider/link", headers={"x-csrf-token": csrf})
    assert started.status_code == 200
    assert started.json()["authorization_url"].startswith("https://issuer.example.test/authorize?")
    state = parse_qs(urlparse(started.json()["authorization_url"]).query)["state"][0]
    flow = _read_flow(auth_client, state)
    monkeypatch.setattr(oidc, "_exchange_code", lambda *_: _async({"id_token": _id_token(private, nonce=flow["nonce"], email="owner@example.test")}))
    monkeypatch.setattr(oidc, "_get_json", lambda _: _async(jwks))
    linked = _callback(auth_client, state)
    assert linked.status_code == 303
    assert auth_client.get("/api/auth/me").json()["username"] == "owner"

    async def identities():
        engine = create_async_engine(auth_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            return list(await session.scalars(select(UserIdentity)))
    assert len(asyncio.run(identities())) == 1


def test_admin_user_management_and_disablement_revoke_sessions(auth_client):
    admin = auth_client.post("/api/auth/setup", json={"username": "admin", "password": "a-very-long-password"})
    assert admin.status_code == 201
    csrf = auth_client.cookies["aic_csrf"]
    second = auth_client.post("/api/auth/register", json={"username": "second", "password": "another-long-password"})
    assert second.status_code == 201
    user_id = second.json()["id"]
    old_session_cookie = auth_client.cookies["aic_session"]
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]})
    auth_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    assert auth_client.get("/api/admin/users").status_code == 200
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]})
    auth_client.post("/api/auth/login", json={"username": "second", "password": "another-long-password"})
    user_csrf = auth_client.cookies["aic_csrf"]
    assert auth_client.get("/api/admin/users").status_code == 403
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": user_csrf})
    auth_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    csrf = auth_client.cookies["aic_csrf"]
    disabled = auth_client.patch(f"/api/admin/users/{user_id}", headers={"x-csrf-token": csrf}, json={"disabled": True})
    assert disabled.status_code == 200 and disabled.json()["disabled"] is True
    assert auth_client.get("/api/auth/me").status_code == 200
    disabled_client = TestClient(auth_client.app)
    disabled_client.cookies.set("aic_session", old_session_cookie)
    assert disabled_client.get("/api/auth/me").status_code == 401

    async def no_sessions():
        engine = create_async_engine(auth_client.app.state.test_database_url)
        factory = async_sessionmaker(engine)
        async with factory() as session:
            user = await session.get(User, user_id)
            assert user is not None and user.disabled
            return list(await session.scalars(select(ApiToken).where(ApiToken.user_id == user_id)))
    assert asyncio.run(no_sessions()) == []


def test_disabling_user_rejects_local_and_oidc_login(auth_client, monkeypatch, oidc_keys):
    private, jwks = oidc_keys
    auth_client.app.state.settings.oidc_providers = [_provider()]
    admin = auth_client.post("/api/auth/setup", json={"username": "admin", "password": "a-very-long-password"})
    assert admin.status_code == 201
    normal = auth_client.post("/api/auth/register", json={"username": "normal", "password": "another-long-password"})
    assert normal.status_code == 201
    user = normal.json()

    async def attach_identity():
        engine = create_async_engine(auth_client.app.state.test_database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(UserIdentity(user_id=user["id"], issuer=ISSUER, subject="subject-1"))
            await session.commit()
        await engine.dispose()

    asyncio.run(attach_identity())
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]})
    auth_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    admin_csrf = auth_client.cookies["aic_csrf"]
    auth_client.patch(
        f"/api/admin/users/{user['id']}",
        headers={"x-csrf-token": admin_csrf},
        json={"disabled": True},
    )
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]})
    local_login = auth_client.post(
        "/api/auth/login", json={"username": user["username"], "password": "another-long-password"}
    )
    assert local_login.status_code == 401

    _mock_discovery(monkeypatch)
    monkeypatch.setattr(oidc, "_get_json", lambda _: _async(jwks))
    state = _begin(auth_client)
    flow = _read_flow(auth_client, state)
    monkeypatch.setattr(
        oidc,
        "_exchange_code",
        lambda *_: _async({"id_token": _id_token(private, nonce=flow["nonce"])}),
    )
    assert _callback(auth_client, state).status_code == 401


def test_admin_cannot_demote_self_or_last_active_admin(auth_client):
    response = auth_client.post("/api/auth/setup", json={"username": "admin", "password": "a-very-long-password"})
    user_id = response.json()["id"]
    result = auth_client.patch(f"/api/admin/users/{user_id}", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]}, json={"role": "user"})
    assert result.status_code == 409


def test_admin_can_change_role_but_cannot_disable_last_admin(auth_client):
    admin = auth_client.post(
        "/api/auth/setup", json={"username": "admin", "password": "a-very-long-password"}
    )
    assert admin.status_code == 201
    user = auth_client.post(
        "/api/auth/register", json={"username": "normal", "password": "another-long-password"}
    )
    auth_client.post("/api/auth/logout", headers={"x-csrf-token": auth_client.cookies["aic_csrf"]})
    auth_client.post("/api/auth/login", json={"username": "admin", "password": "a-very-long-password"})
    csrf = auth_client.cookies["aic_csrf"]
    promoted = auth_client.patch(
        f"/api/admin/users/{user.json()['id']}",
        headers={"x-csrf-token": csrf},
        json={"role": "admin"},
    )
    assert promoted.status_code == 200 and promoted.json()["role"] == "admin"


def test_oidc_provider_settings_require_https_and_unique_names():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OidcProviderSettings(name="bad", issuer_url="http://issuer.test", client_id="id", client_secret="secret")
    provider = _provider()
    with pytest.raises(ValidationError):
        Settings(_env_file=None, oidc_providers=[provider, provider])
