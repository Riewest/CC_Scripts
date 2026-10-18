# REQ-007 Computer registration flow
Status: todo | Milestone: M1 | Depends: REQ-004, REQ-005, REQ-006

## Goal
Fast, easy onboarding: an "Add computer" flow in the UI that yields a full pasteable command, for personal or team ownership.

## Design notes
- API: `POST /api/pairing-codes` with `owner` (me or team id) and optional label; returns a 6-char code (unambiguous alphabet, e.g. no 0/O/1/I), expiry (default 15 min, single use), and ready-to-paste command: `wget run https://HOST/install/CODE` (host from `AIC_PUBLIC_URL`).
- The code is stored hashed; exchange happens during first `hello` (REQ-005); on success the computer row is created under the owner, with a device secret returned once.
- UI wizard: choose owner (me or a team), optional label, press Generate, show the command with a copy button and countdown, then live-wait for the computer to appear and confirm.
- Re-registration: existing computer can generate a re-pair code that keeps identity but rotates the secret.
- Also offer manual entry path: run `aicontrol pair` on the computer and enter the code shown in the UI.
- Team ownership requires the user be a team owner/member with permission (rules finalised in REQ-011; until then personal only, with the owner parameter accepted and validated).

## Acceptance criteria
- [ ] Code is single-use, expires, and cannot be brute-forced (rate limited, hashed).
- [ ] Generated command contains the correct public URL and works end to end (manual).
- [ ] New computer appears under the chosen owner and shows live in the wizard.
- [ ] Secret rotation on re-pair invalidates the old secret.

## Test plan
pytest: code generation/expiry/reuse, pairing via fake client, rate limiting, re-pair rotation.

## Files touched
`server/aicontrol/pairing/**`, `web/src/pages/AddComputer.tsx`, tests.
