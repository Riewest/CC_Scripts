# REQ-008 MVP web UI
Status: todo | Milestone: M1 | Depends: REQ-006, REQ-007

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
- [ ] Dashboard updates live when computers connect, disconnect, or send telemetry.
- [ ] Running code shows output and errors with traceback.
- [ ] Stop interrupts a running program; Emergency stop works even with a queued run.
- [ ] Offline computers show as offline and disable run controls.
- [ ] UI builds and is served by the server; no secrets in the bundle.

## Test plan
pytest: exec/interrupt endpoints with fake client, permission denial for non-owner. Manual: STOP POINT 1 checklist.

## Files touched
`web/**`, `server/aicontrol/api/computers.py`, tests.
