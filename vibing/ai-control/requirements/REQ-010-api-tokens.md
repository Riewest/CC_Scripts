# REQ-010 API tokens
Status: done | Milestone: M2 | Depends: REQ-006

## Goal
Scoped, revocable API tokens for programmatic access (scripts, MCP, CI).

## Design notes
- Token format `aic_<random>`; show once; store only a hash and a short prefix for display.
- Scopes: `computers:read`, `computers:exec`, `scripts:rw`, `ai:use`, `admin`. A token can be limited to specific computers or groups.
- Optional expiry; last-used timestamp and IP.
- `Authorization: Bearer` accepted by the same `current_user` dependency; tokens never exceed the owning user's own permissions.
- UI page to create, list, and revoke tokens.

## Acceptance criteria
- [x] Token shown once and stored hashed; only a short display prefix and non-secret metadata are returned thereafter.
- [x] Scope and computer/group restrictions enforced on all current protected API endpoints; bearer access cannot bypass CSRF-protected pairing or token management.
- [x] Revoked and expired tokens are rejected immediately; disabled-user credentials are also rejected.
- [x] Token authentication updates last-used time/IP and identifies token principals for REQ-013 audit hooks.

## Test plan
pytest: create/use/revoke, scope denial, restricted-computer denial, expiry.

## Files touched
`server/aicontrol/auth/tokens.py`, `web/src/pages/Tokens.tsx`, tests.
