# REQ-012 Groups and sharing
Status: done | Milestone: M2 | Depends: REQ-011

## Goal
Computer groups that can be shared, plus per-computer sharing, with viewer/operator/owner roles.

## Design notes
- Group: named set of computers owned by a user or team; a computer may be in many groups.
- Share: grant a user or team a role on a computer or on a whole group. Roles: viewer (see telemetry, runs, terminal read-only), operator (run code, interrupt, use AI, files read), owner (everything incl. sharing, delete, re-pair).
- Effective role = highest of all grants. Revoking is immediate and disconnects live subscriptions (UI websockets).
- Share links are out of scope.
- UI: group management, share dialog, "shared with me" section.

## Acceptance criteria
- [x] Group CRUD and membership management (personal/team ownership, computer add/remove, ownership constraints).
- [x] Share to user/team on computer or group; revoke, with owner-level grant administration and redundant/incompatible grants rejected.
- [x] Current computer APIs and UI WebSocket subscriptions use centralized `effective_role`; viewers can read telemetry/runs but cannot execute, interrupt, reboot or re-pair.
- [x] Revocation changes access immediately for new HTTP requests and closes existing UI subscriptions within 15 seconds (automated test shortens interval and verifies socket closure).

## Test plan
pytest: role matrix per endpoint category, revocation of live subscription, group inheritance.

## Files touched
`server/aicontrol/groups/**`, `server/aicontrol/sharing/**`, `web/**`, tests.
