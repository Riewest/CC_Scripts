# REQ-013 Audit log
Status: done | Milestone: M2 | Depends: REQ-008

## Goal
Immutable record of every command, script, AI action and result, with viewer UI.

## Design notes
- `audit_events`: time, actor (user, token, AI session, system), computer, action, payload (code, params, result summary), outcome, source IP.
- Write via a single `audit.record()` helper called from exec, interrupt, file ops, peripheral calls, sharing changes, auth events, AI tool calls.
- Append-only: no update/delete endpoints; retention setting for pruning by admin.
- Redact secrets (tokens, API keys, passwords) before storing.
- UI: filter by computer, actor, action, time; export JSON/CSV; per-computer activity tab.
- Visibility: owners and admins see all for their computers; operators see their own.

## Acceptance criteria
- [x] All currently implemented control-plane actions in scope produce events through the unified audit writer; unimplemented future file/peripheral/AI actions will use this same hook when those features are introduced.
- [x] Secrets (passwords, OIDC flow values, API/device/pairing tokens, authorization/cookie/CSRF values) are redacted before persistence; tests cover nested and inline secrets.
- [x] Audit events are ORM append-only; no edit/delete API exists. Explicit retention pruning is administrator-only, requires a cutoff at least one day old, and itself emits an event.
- [x] Visibility, filters (computer, actor user/token/type, action, outcome, time), pagination, JSON/CSV export work; CSV formula cells are neutralized.

## Test plan
pytest: event creation per action, redaction, visibility rules, pagination.

## Files touched
`server/aicontrol/audit/**`, `web/src/pages/Audit.tsx`, tests.
