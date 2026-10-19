# REQ-008 MVP web UI
Status: done | Milestone: M1 | Depends: REQ-006, REQ-007

## Goal
The minimum UI to control computers: log in, see computers live, run Lua, see output and errors, stop programs.

## Design notes
- React + TS, router, a typed API client (generated from FastAPI OpenAPI), a WebSocket hook for live updates (`/ws/ui`) fed by the gateway event bus.
- Pages: Login/Setup, Dashboard (cards grouped by kind with status, fuel, label, last seen), Computer detail (telemetry, inventory grid for turtles, peripherals list, Lua editor with run button, output pane with stdout/return/error+traceback, run history), Add Computer (REQ-007).
- Buttons: Run, Stop (interrupt), Emergency stop (interrupt and clear queue), Reboot, Rename.
- Lua editor: Monaco or CodeMirror with Lua highlighting.
- Execution is recorded in a `runs` history (code, started, finished, result) for later audit use.
- Server endpoints: `POST /api/computers/{id}/exec`, `POST /api/computers/{id}/interrupt`, `POST /api/computers/{id}/reboot`, `GET /api/computers`, `GET /api/computers/{id}`, `GET /api/computers/{id}/runs`.
- Only the owner can act (sharing arrives in REQ-012).

## Acceptance criteria
- [x] Dashboard subscribes to authenticated, owner-filtered live online/offline/telemetry/run events and persists current telemetry for reload.
- [x] Running code returns and displays stdout, return values, errors, and traceback; run records are saved.
- [x] Stop interrupts an active run; emergency stop sends out-of-band and cancels queued executions.
- [x] Offline computers show as offline and disable run/reboot controls.
- [x] UI builds and is served by the server; session/device secrets are not embedded in the bundle.

## Test plan
pytest: exec/interrupt endpoints with fake client, permission denial for non-owner. Completed manual STOP POINT 1 results are archived in `requirements/manual-validation/M0-M1-validation-record.md`.

## Files touched
`web/**`, `server/aicontrol/api/computers.py`, tests.

## Archived manual verification

Completed M1 manual acceptance was verified on 2026-10-19. The full results are retained in [M0/M1 validation record](manual-validation/M0-M1-validation-record.md), not as a user-facing setup guide. It records setup/pairing, output and return values, compile/runtime tracebacks, sleep and tight-loop interrupts, emergency queued cancellation, reconnect, owner isolation, turtle telemetry/equipment/peripherals, copyable `X Y Z` coordinates, and event-triggered telemetry refresh. STOP POINT 1 is complete.

## Pairing countdown timezone fix

SQLite returns naive UTC expiry datetimes. The pairing API now serializes them with an explicit `+00:00` offset so browsers in non-UTC zones show the correct remaining duration instead of adding their local offset. API regression assertions cover both initial create and status polling responses.
