# REQ-004 WebSocket gateway
Status: done | Milestone: M1 | Depends: REQ-002, REQ-003

## Goal
Server endpoint that accepts computer connections, tracks them, and offers request/response calls to higher layers.

## Design notes
- Endpoint `/ws/computer`. First message must be `hello` within a timeout; validate device secret against `computers.device_secret_hash`; reject and close otherwise.
- `ConnectionRegistry`: computer id to live connection; replaces a stale duplicate connection.
- `call(computer_id, message, timeout)` returns the correlated reply; supports streaming replies for later REQs.
- Heartbeat with server-side timeout marking computers offline; update `last_seen`.
- Pub/sub of internal events (online, offline, telemetry, exec results) via an async event bus for the UI (REQ-008) to subscribe to.
- Interrupt: `interrupt` message handled out of band, never queued behind `exec`.
- All client-reported errors are stored and forwarded.

## Acceptance criteria
- [x] Valid hello connects; invalid or missing hello is closed with a reason.
- [x] Duplicate connection for same computer replaces the old one.
- [x] `call()` times out cleanly and cleans pending state.
- [x] Offline detection via missed heartbeats updates DB status and emits an event.
- [x] Oversized or malformed frames do not crash the server.

## Test plan
pytest with a fake CC WebSocket client: connect, heartbeat, exec round trip, timeout, duplicate connect, bad auth.

## Files touched
`server/aicontrol/gateway/**`, `server/tests/test_gateway.py`, `server/tests/fakecc.py`.
