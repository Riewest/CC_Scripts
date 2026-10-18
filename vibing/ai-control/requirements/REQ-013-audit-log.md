# REQ-013 Audit log
Status: todo | Milestone: M2 | Depends: REQ-008

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
- [ ] All actions listed above produce events.
- [ ] Secrets are redacted.
- [ ] No API can modify or delete events except retention pruning by admin.
- [ ] Filtering, pagination and export work.

## Test plan
pytest: event creation per action, redaction, visibility rules, pagination.

## Files touched
`server/aicontrol/audit/**`, `web/src/pages/Audit.tsx`, tests.
