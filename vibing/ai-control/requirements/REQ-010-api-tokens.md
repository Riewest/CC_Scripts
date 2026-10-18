# REQ-010 API tokens
Status: todo | Milestone: M2 | Depends: REQ-006

## Goal
Scoped, revocable API tokens for programmatic access (scripts, MCP, CI).

## Design notes
- Token format `aic_<random>`; show once; store only a hash and a short prefix for display.
- Scopes: `computers:read`, `computers:exec`, `scripts:rw`, `ai:use`, `admin`. A token can be limited to specific computers or groups.
- Optional expiry; last-used timestamp and IP.
- `Authorization: Bearer` accepted by the same `current_user` dependency; tokens never exceed the owning user's own permissions.
- UI page to create, list, and revoke tokens.

## Acceptance criteria
- [ ] Token shown once and stored hashed.
- [ ] Scope and computer restrictions enforced on every endpoint.
- [ ] Revoked and expired tokens are rejected immediately.
- [ ] Token use appears in the audit log once REQ-013 exists (hook in place).

## Test plan
pytest: create/use/revoke, scope denial, restricted-computer denial, expiry.

## Files touched
`server/aicontrol/auth/tokens.py`, `web/src/pages/Tokens.tsx`, tests.
