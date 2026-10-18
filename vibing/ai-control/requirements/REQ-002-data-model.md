# REQ-002 Data model and migrations
Status: todo | Milestone: M0 | Depends: REQ-001

## Goal
SQLAlchemy 2 models and Alembic migrations for everything the plan needs, portable to Postgres.

## Design notes
Use UUID primary keys (string), UTC timestamps, soft constraints via FKs.
Tables: `users` (username, password_hash nullable, role, oidc identities in `user_identities`), `teams`, `team_members` (role owner/member), `computers` (owner_user_id XOR owner_team_id, label, kind computer/turtle/pocket, advanced flag, cc_version, last_seen, status, device_secret_hash), `pairing_codes` (code hash, owner, expiry, used_at), `groups` (owner user/team), `group_members`, `shares` (subject user/team, target computer/group, role viewer/operator/owner), `scripts` (+ `script_versions`), `api_tokens`, `audit_events`, `ai_providers` (encrypted keys), `ai_sessions`, `ai_messages`, `goals`, `goal_steps`.
Later REQs may add columns via new migrations; do not pre-build logic.

## Acceptance criteria
- [ ] Models for all tables above exist with relationships and indexes on lookup columns.
- [ ] Alembic initial migration applies cleanly to an empty SQLite DB and `alembic check` reports no drift.
- [ ] Ownership constraint: a computer has exactly one of user/team owner (CHECK constraint).
- [ ] Async session dependency for FastAPI plus a test fixture using an in-memory DB.
- [ ] Secrets (passwords, device secrets, tokens) are stored hashed; provider keys are encrypted with a key from settings.

## Test plan
pytest: migration up/down, constraint violations, CRUD smoke tests per model.

## Files touched
`server/aicontrol/db/**`, `server/alembic/**`, `server/tests/test_models.py`.
