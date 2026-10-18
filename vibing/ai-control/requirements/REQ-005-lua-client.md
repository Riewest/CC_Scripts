# REQ-005 Lua client and installer
Status: todo | Milestone: M1 | Depends: REQ-003, REQ-004

## Goal
A Lua client that installs with one command, stays connected, runs server-sent code, can be interrupted, and reports all errors.

## Design notes
- Served by the server: `GET /install` returns an installer script; `GET /client/manifest.json` lists files with hashes; `GET /client/<file>`.
- Installer (`wget run https://host/install?code=ABC123` style, exact form defined with REQ-007): downloads client files, writes `/aicontrol/config` (server URL, pairing code), writes `startup.lua`, reboots.
- `startup.lua` checks the manifest on boot and self-updates files, then starts the client; `update_client` message also triggers an update.
- Pairing: first connect uses the pairing code in `hello`; server replies with a device secret stored in `/aicontrol/device`; later connects use the secret.
- Runner: executes code with `load(code, "=remote", "t", env)` in a coroutine; the main loop uses `parallel.waitForAny` over the WebSocket reader and the running program so an `interrupt` message terminates the program coroutine. Captures `print`/`write` output and return values; sends `exec_result` with error message plus traceback via `xpcall` and `debug.traceback`.
- Program environment is a copy of `_ENV` with `print` redirected to the capture buffer (and the real terminal).
- Telemetry on connect and every N seconds: id, label, kind, advanced, version, uptime, day/time; turtle fuel, fuel limit, selected slot, inventory (16 slots with item details), equipped tools; list of attached peripherals with types; position via INS if `/squid/INS.lua` exists, otherwise GPS if available.
- Reconnect with exponential backoff; never crash the main loop; log to `/aicontrol/log`.
- Known limit: an in-flight `turtle.*` call cannot be aborted; interrupt takes effect at the next yield. Document and report this in the interrupt reply.

## Acceptance criteria
- [ ] Installer and `startup.lua` work on computer, turtle and pocket computer (manual checklist).
- [ ] Client reconnects after server restart and network loss.
- [ ] Runtime and compile errors return message and traceback to the server.
- [ ] Interrupt stops a `while true do end` loop within a second (manual) and the fake-client test covers the protocol side.
- [ ] Output and return values are captured and returned, truncated at the size limit with a marker.
- [ ] Self-update replaces changed files and restarts cleanly.
- [ ] Manifest and file endpoints implemented and tested server-side.

## Test plan
pytest: manifest hashes, install script content, file serving, pairing handshake with fake client. In-game: items above recorded in PLAN.md STOP POINT 1.

## Files touched
`client/**`, `server/aicontrol/client_dist/**`, `docs/client.md`.
