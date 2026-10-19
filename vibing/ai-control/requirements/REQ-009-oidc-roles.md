# REQ-009 OIDC login and roles
Status: done | Milestone: M2 | Depends: REQ-006

## Goal
Generic OIDC login (Google, GitHub via compatible provider, Keycloak, Authentik, etc.) alongside local auth, and a working admin/user role model.

## Design notes
- Config via env/settings: one or more providers with name, issuer URL (discovery), client id/secret, scopes, optional allowed email domains, auto-create users toggle.
- Authorization code flow with PKCE, `state` and `nonce` validated, ID token signature verified via JWKS (use authlib or similar).
- `user_identities` links (provider, subject) to a user; link to an existing account only when the user is logged in and confirms (no automatic email-based takeover).
- Login page shows configured providers.
- Roles: `admin` can manage users, teams, settings; `user` default. Admin UI for user list, role change, disable user.

## Acceptance criteria
- [x] Login via a configured OIDC provider creates or logs in the right user (mocked signed-JWKS flow covers both first login and returning identity).
- [x] State/nonce/PKCE failures are rejected (browser-bound one-use state, missing browser cookie, wrong nonce, bad signature, invalid expiry, and PKCE S256 challenge tests).
- [x] Account linking requires an authenticated session and explicit CSRF-protected initiation; linking never matches by email.
- [x] Disabled users cannot log in by any method; their sessions and stored tokens are revoked, and live UI sockets revalidate within 15 seconds.
- [x] Admin-only endpoints return 403 to normal users; administrator user/role/disable controls protect the last active administrator.
- [x] docs/auth.md has provider setup examples and deployment/security notes.

## Test plan
pytest with a mocked OIDC provider (discovery, JWKS, token endpoint): success, bad nonce, bad signature, domain restriction, link flow.

## Files touched
`server/aicontrol/auth/oidc.py`, `web` login and admin pages, `docs/auth.md`.
