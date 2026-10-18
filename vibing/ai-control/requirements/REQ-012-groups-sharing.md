# REQ-012 Groups and sharing
Status: todo | Milestone: M2 | Depends: REQ-011

## Goal
Computer groups that can be shared, plus per-computer sharing, with viewer/operator/owner roles.

## Design notes
- Group: named set of computers owned by a user or team; a computer may be in many groups.
- Share: grant a user or team a role on a computer or on a whole group. Roles: viewer (see telemetry, runs, terminal read-only), operator (run code, interrupt, use AI, files read), owner (everything incl. sharing, delete, re-pair).
- Effective role = highest of all grants. Revoking is immediate and disconnects live subscriptions (UI websockets).
- Share links are out of scope.
- UI: group management, share dialog, "shared with me" section.

## Acceptance criteria
- [ ] Group CRUD and membership management.
- [ ] Share to user/team on computer or group; revoke.
- [ ] Every API endpoint and WS subscription uses `effective_role`; viewer cannot exec.
- [ ] Revocation takes effect on open UI sockets within seconds.

## Test plan
pytest: role matrix per endpoint category, revocation of live subscription, group inheritance.

## Files touched
`server/aicontrol/groups/**`, `server/aicontrol/sharing/**`, `web/**`, tests.
