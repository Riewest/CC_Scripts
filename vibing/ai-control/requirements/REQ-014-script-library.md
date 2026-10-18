# REQ-014 Script library and repo import
Status: todo | Milestone: M3 | Depends: REQ-008

## Goal
Saved, versioned Lua scripts on the server that can be run on computers, and import of the existing repo scripts.

## Design notes
- Script: name, description, tags, owner (user/team), visibility (private/team/shared), parameters schema (name, type, default), versions with author (user or AI) and diff.
- Run a script: server renders parameters into a preamble (`local params = {...}`) then execs; run recorded in history and audit.
- Send as file: option to write the script to the computer's disk (via file ops, REQ-017) instead of executing.
- Import: admin tool scans a configured path (default this repo's root) and imports `.lua` files with path-based tags; idempotent by path+hash.
- Editor with Lua highlighting, version history, restore.

## Acceptance criteria
- [ ] CRUD with versioning and restore.
- [ ] Parameters rendered safely (proper Lua string escaping, tested with hostile input).
- [ ] Import of repo scripts is idempotent and tags by folder.
- [ ] Visibility rules respected.

## Test plan
pytest: versioning, param escaping, import idempotency, permissions.

## Files touched
`server/aicontrol/scripts/**`, `web/src/pages/Scripts.tsx`, tests.
