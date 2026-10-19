# REQ-007 Computer registration flow
Status: done | Milestone: M1 | Depends: REQ-004, REQ-005, REQ-006

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
- [x] Code is single-use, expires, and cannot be brute-forced (rate limited, hashed).
- [x] Generated command contains the configured public URL and works end to end (manual in-game verification).
- [x] New computer appears under the chosen owner and shows live in the wizard (manual UI verification).
- [x] Secret rotation on re-pair invalidates the old secret.

## Test plan
pytest: code generation/expiry/reuse, pairing via fake client, rate limiting, re-pair rotation.

## Manual verification
- Log in to the MVP UI, open Add computer, generate a personal pairing command, copy it, and run it on a fresh CC:Tweaked device. Confirm the new device appears in this wizard and as online on the dashboard.
- Verify the generated command uses `AIC_PUBLIC_URL` (set it to the host/LAN address reachable by Minecraft computers if that differs from the browser address).
- From an owned computer detail view, choose Re-pair, run the new command on that same device, and confirm its identity remains the same while the old device secret no longer reconnects.

## Files touched
`server/aicontrol/pairing/**`, `web/src/pages/AddComputer.tsx`, tests.
