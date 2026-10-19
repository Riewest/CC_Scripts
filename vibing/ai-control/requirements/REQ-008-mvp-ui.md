# REQ-008 MVP web UI
Status: blocked | Milestone: M1 | Depends: REQ-006, REQ-007

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
pytest: exec/interrupt endpoints with fake client, permission denial for non-owner. Manual: STOP POINT 1 checklist.

## Files touched
`web/**`, `server/aicontrol/api/computers.py`, tests.

## Manual MVP verification addendum

The integrated M1 stop-point checks below require a real CC:Tweaked server and authenticated browser. Run Docker from `vibing/ai-control` with `docker compose up -d --build`, then open `http://localhost:8000`. The existing local database has a passwordless `manual-test-owner` with the three previously paired devices, but initial setup has already been completed by `riewest14`; there is currently no supported password-recovery path for the passwordless owner. Sign in as the account you can access and pair a fresh/test device to it. Do not silently reassign device ownership or reset account data.

1. Sign in and confirm the dashboard lists devices owned by that account. The existing devices owned by `manual-test-owner` will not appear under `riewest14`. Use Add Computer to generate and copy a pairing command, paste it into a fresh/test CC computer shell, and confirm the wizard changes from waiting to paired/online.
2. **Verified on Computer 15:** run this harmless check:

   ```lua
   print("hello from AI Control")
   write("write output")
   return 42, "done"
   ```

	Confirm the UI shows captured output and both return values. Check Recent runs for the persisted run record.
3. **Verified on Computer 15 after refreshing the client:** test compile and runtime error rendering separately:

   ```lua
   local = broken
   ```

   ```lua
   error("intentional runtime test")
   ```

	Confirm each displays its error and traceback in the result panel/history.
4. Run `while true do end`, press Stop, and verify completion with an interrupted result. **Also verified on Computer 15:** a loop that prints and calls `os.sleep(1)` ran repeatedly, then Stop interrupted it and returned the captured output. To verify emergency queue clearing, open the same computer in a second browser tab/session, start one long program in each, then press Emergency stop. Confirm the active program stops and queued program(s) are returned as cancelled. Do not run this on a turtle while it is doing unsafe work.
5. **Partially verified on Computer 14 (turtle):** after rebooting to install the client update, `turtle.refuel(64)` ran without an execution/coroutine error. The detailed equipped-item JSON row has been removed; the dashboard keeps the compact fuel/slot/position tiles and inventory grid. Still check fuel, selected slot, 16-slot inventory grid, peripherals and position fields; use Reboot only when safe and verify it reconnects.
6. Stop/restart Docker with the REQ-005 addendum procedure; the UI should show offline, then live status/telemetry again when each client reconnects.
7. Sign out and verify `/api/computers` is no longer accessible without logging in. Sign in as another account (if signup has been enabled for testing) and verify it cannot see the first owner's devices.

The harmless output/return-value check, both compile/runtime traceback checks, and Stop during a timer-based `os.sleep(1)` loop passed on Computer 15 on 2026-10-19. The turtle API invocation passed on Computer 14; remaining integrated M1 STOP POINT 1 checks are fresh pairing, the tight busy-loop interrupt, emergency queue cancellation, full turtle/pocket telemetry inspection, and Docker stop/start reconnect. Record those outcomes before proceeding to M2.

## Pairing countdown timezone fix

SQLite returns naive UTC expiry datetimes. The pairing API now serializes them with an explicit `+00:00` offset so browsers in non-UTC zones show the correct remaining duration instead of adding their local offset. API regression assertions cover both initial create and status polling responses.
