# M0/M1 Manual Validation Record — Completed

**Status:** Complete  
**Verified:** 2026-10-19  
**Purpose:** Archived acceptance evidence for M0/M1. This is a historical record, not an end-user setup guide or an active checklist.

## Test setup

- Docker Compose service at `http://localhost:8000`.
- Test account owned Computer 15 (computer) and Computer 14 (turtle). A pocket computer was paired to the accessible test account during this validation.
- Older Computer 10 (pocket), Computer 11 (computer), and Computer 12 (turtle) belong to a separate test account; ownership was not changed.

## Results

### Install, pairing, and reconnect

- [x] CC:Tweaked installer/startup/pairing verified across computer, turtle, and pocket types.
- [x] New pocket paired through the Add Computer wizard and appeared online under the test account; its UI run returned output and a value.
- [x] Reboot and Docker restart/short outage recovery verified; clients reconnected and returned online using saved device credentials.
- [x] Client startup manifest downloaded updated client files and restarted cleanly without changing device identity.

### Login and ownership

- [x] Signed-out `GET /api/computers` returned HTTP 401 with `{"detail":"Authentication required"}`.
- [x] Owner-isolation behavior is covered by automated tests; device records were not reassigned during manual validation.

### Remote execution

- [x] Computer 15 captured both output functions and multiple return values:

  ```lua
  print("hello from AI Control")
  write("write output")
  return 42, "done"
  ```

- [x] Compile error `local = broken` and runtime error `error("intentional runtime test")` displayed their error and traceback in the UI without disconnecting the client.
- [x] `os.sleep(1)` loop ran and printed repeatedly; Stop interrupted it while the computer remained online.
- [x] Tight non-yielding loop `while true do end` stopped in under one second on Computer 15. UI showed `Interrupted`; the connection remained live.
- [x] Emergency stop was tested with an active and queued program in two tabs. Active result was `Interrupted`; queued result was `Cancelled by emergency stop`; both requests completed and the computer stayed online.
- [x] Turtle API call `turtle.refuel(64)` completed on Computer 14 without a sandbox/coroutine error. No hazardous turtle movement was used for these checks.

### Turtle telemetry and display

- [x] Fuel, fuel limit, selected slot, 16-slot inventory, left/right equipment, and attached peripheral names/types were visible and matched the turtle.
- [x] Equipped item is displayed as parsed details (for example, `Diamond Pickaxe · 1561/1561 durability`), not raw JSON. Full item metadata remains collected for future features.
- [x] INS/GPS coordinates render in the UI as space-separated `X Y Z` (for example, `-131 73 24`), not JSON. The **Copy** control copies those exact three values; the Z coordinate is no longer clipped.
- [x] Telemetry refreshes after remote program completion and immediately after peripheral attach/detach events; periodic heartbeat telemetry remains a fallback. This addressed the observed delay after `turtle.select(15)` and modem attachment without adding polling.
- [x] Peripheral list intentionally shows attached peripheral names/types (for example, side `left`, type `modem`). Richer modem-specific context is deferred to the later Peripheral Explorer requirement.

## Automated verification at closure

- Ruff clean.
- 85 backend tests passed (one upstream Starlette/httpx deprecation warning).
- Frontend TypeScript/Vite production build passed.
- Docker health endpoint returned `{"status":"ok"}` after rebuild.

## Outcome

M0 has no manual acceptance requirements. M1 STOP POINT 1 is complete based on the above manual checks and automated validation. Any later re-verification should be added as a new dated entry rather than reopening this archived record unless a regression is found.
