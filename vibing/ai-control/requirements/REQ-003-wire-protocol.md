# REQ-003 Wire protocol spec
Status: todo | Milestone: M0 | Depends: REQ-001

## Goal
A versioned JSON protocol between the Lua client and server, documented and implemented as Pydantic models.

## Design notes
- Envelope: `{"v":1,"type":"...","id":"<req id, optional>","reply_to":"<id, optional>","data":{...}}`.
- Client to server: `hello` (device id, secret, kind, label, cc version, client version, capabilities), `heartbeat`, `telemetry`, `exec_result` (ok, return values, captured output, error, traceback, duration), `exec_started`, `event`, `term_frame`, `fs_result`, `peripheral_result`.
- Server to client: `hello_ack` (accept, session id, heartbeat interval, limits), `exec` (code, name, timeout, id), `interrupt`, `update_client` (version, files or url), `fs_op`, `peripheral_call`, `term_input`, `config`.
- Errors: `error` with code and message; unknown types ignored with a log.
- CC constraints: websocket messages default max 128 KiB; define chunking (`chunk` field: index/total) for larger payloads; messages are text frames (JSON via `textutils.serializeJSON`, note it cannot represent sparse arrays or NaN, document workarounds).
- Auth on connect: device secret in `hello`, never in the URL query.

## Acceptance criteria
- [ ] `docs/protocol.md` describes every message with examples and the chunking rules.
- [ ] Pydantic models for all messages with a discriminated union and version field.
- [ ] Unknown message types and bad payloads are rejected without crashing.
- [ ] Chunk split/reassemble helpers with size limit setting.

## Test plan
pytest: round-trip each model, invalid payloads, chunk reassembly out-of-order and oversize.

## Files touched
`docs/protocol.md`, `server/aicontrol/protocol/**`, `server/tests/test_protocol.py`.
