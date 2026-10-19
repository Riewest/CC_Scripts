# M0/M1 Manual Validation Checklist

This file consolidates only the real browser/ComputerCraft checks that remain before M1 can be closed. M0 has no outstanding manual checks. Automated work is complete; keep M1 at STOP POINT 1 until the remaining boxes below are checked and the outcomes recorded.

**Current test setup (checked 2026-10-19):** Docker Compose is running at `http://localhost:8000`. The signed-in test account `riewest14` owns Computer 15 (computer) and Computer 14 (turtle), both online. The older Computer 10 (pocket), Computer 11 (computer), and Computer 12 (turtle) belong to `manual-test-owner`; don’t reassign them or reset the database. Use `riewest14` for additional test devices.

## Already verified — no need to repeat

- [x] Fresh CC:Tweaked installation and reconnect on computer, turtle and pocket types; earlier Docker outage/restart recovery was also tested.
- [x] Computer 15 printed and wrote output and returned both `42` and `"done"` to the UI.
- [x] Compile and runtime errors displayed messages and tracebacks without disconnecting.
- [x] A repeated `os.sleep(1)` loop printed output and stopped on request.
- [x] Computer 14 accepted remote `turtle.refuel(64)`; equipment is collected and rendered as parsed left/right item details (e.g. item name and durability).
- [x] Pocket pairing/run, tight-loop Stop, Emergency stop queue cancellation, Docker reconnect, and signed-out fleet API denial were manually confirmed. The emergency-stop outputs were `Interrupted` for the active run and `Cancelled by emergency stop` for the queued run.
- [x] Authentication, ownership, pairing expiry/rate-limit/rotation, gateway protocol, and API behavior are covered by automated tests.

## Manual validation record

### 1. Add a pocket computer to the accessible test account

**Confirmed by user:** pocket pairing and the UI run succeeded; output and return value appeared. No need to repeat.

This checks the integrated Add Computer wizard and exercises the MVP UI on a pocket device owned by `riewest14`. The already-paired pocket belongs to a different account, so it will not appear in this fleet.

1. In the browser, sign in as `riewest14` and click **Add computer**.
2. Enter an optional label such as `M1 pocket test`, generate the command, and use the wizard's **Copy pairing command** button.
3. In a fresh/available CC:Tweaked pocket computer shell, paste the exact command copied from the UI. Don’t type a placeholder code and don’t share the one-time code or `/aicontrol/config`.
4. Confirm the wizard reports the device paired/online and the dashboard shows it online under `riewest14`.
5. On that pocket computer, run this harmless check in the web UI and confirm output and return value appear:

   ```lua
   print("pocket UI test")
   return os.getComputerID()
   ```

   (If Computer 15 was paired through this same Add Computer UI flow and its wizard confirmation was observed, that part is already satisfied; pairing the pocket still verifies the remaining device type.)

### 2. Stop a tight, non-yielding loop

**Confirmed by user:** Computer 15 returned `Interrupted` in under a second and stayed online. Observed result:

```
EXECUTION ERROR
Interrupted

Execution interrupted. An in-flight turtle API call cannot be aborted; interruption takes effect at the next Lua instruction yield.
```

Use **Computer 15 only**, not a turtle performing work. The loop deliberately has no sleep or event calls.

1. Set the editor to this program and click **Run**:

   ```lua
   while true do end
   ```

2. Click **Stop**. Confirm it returns an `Interrupted` result in under one second, the page remains connected, and Computer 15 remains online.

### 3. Exercise Emergency stop with a queued run

**Confirmed by user:** pressed Emergency stop in tab B; both requests completed and the computer stayed online. Observed active-run result:

```
Interrupted

Execution interrupted. An in-flight turtle API call cannot be aborted; interruption takes effect at the next Lua instruction yield.
```
Observed queued-run result:

```
Cancelled by emergency stop

Execution was cancelled before it started.
```

Use **Computer 15 only**. Open the same computer in two authenticated browser tabs; both tabs should be signed into the same owner account.

1. In tab A, start an active, cancellable program:

   ```lua
   while true do
       os.sleep(1)
   end
   ```

2. While tab A is still running, use tab B to submit a second program to the same computer:

   ```lua
   print("This queued run should be cancelled")
   ```

3. Press **Emergency stop**. Confirm the active run is interrupted and the queued run completes with a cancellation result. Confirm both requests finish and the computer stays online.

### 4. Inspect turtle telemetry in the UI

The user confirmed the telemetry fields and peripheral list below. Richer modem context is out of M1 scope; the current list intentionally reports attached peripheral names/types. Coordinate formatting and event-triggered refresh were implemented after this inspection and need the brief post-deployment verification described at the end.

On Computer 14 (turtle), verify the dashboard reflects current telemetry:

- [x] Fuel, fuel limit and selected slot are populated. Telemetry now refreshes after each remote program completes; peripheral attach/detach triggers a full snapshot. The periodic heartbeat snapshot remains a low-frequency fallback.
- [X] Inventory opens as a 16-slot grid and item names/counts match the turtle.
- [x] Left/right equipment show readable names (not raw JSON); empty sides say **Empty**. Item durability is formatted as current/max. Full equipment metadata remains collected for later use.
- [X] Attached peripherals list names/types in the expandable panel.
   - Confirmed: attached peripheral name/type appears. Richer modem details can be added with the later peripheral-explorer feature.
  ```
  Peripherals · 1 attached

    [
    {
        "name": "left",
        "type": "modem"
    }
    ]
  ```
- [ ] Position data is available, but it previously rendered as clipped JSON. The UI now formats it as `X Y Z` (for example, `-131 73 208`) with a **Copy** button for those three space-separated values. Verify this behavior after deployment and turtle client refresh.

No turtle movement/refueling is needed for this display check.

### 5. Verify reconnect with the currently deployed client

**Confirmed by user:** devices returned online after restart/outage. No need to repeat unless the latest client fails to reconnect.

An earlier version passed outage recovery, but repeat once after the recent client updates. Keep Minecraft and the computers running. In Git Bash/WSL, from the AI Control directory, run each command in its own terminal invocation and wait for the service to return before the next check:

```sh
cd /c/Users/Chase/Documents/Repos/CC_Scripts/vibing/ai-control
```

```sh
docker compose restart ai-control
```

After the service is healthy, refresh the dashboard and confirm Computer 15, Computer 14, and the pocket computer return to online with updated last-seen/telemetry. If you prefer a short outage test instead, use these commands as two separate invocations:

```sh
docker compose stop ai-control
```

```sh
docker compose start ai-control
```

The first health request immediately after startup can race Uvicorn initialization; retry it if it returns an empty response:

```sh
curl.exe --fail http://localhost:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

Do not run `docker compose down -v`; that deletes the persistent database volume.

### 6. Confirm sign-out protects the fleet API

**Confirmed by user:** signed-out request returned HTTP 401. Observed response:

```
{"detail":"Authentication required"}
```

1. Click **Sign out** in the browser.
2. Open this URL in the signed-out browser and confirm it returns HTTP 401 (not the computer list):

   ```text
   http://localhost:8000/api/computers
   ```

3. Sign back in as `riewest14` and confirm its Computer 14/15 fleet is still present. Do not enable public signup just for this check; owner isolation is already tested automatically.

## Completion record

2026-10-19: User confirmed pocket pairing/run, sub-second tight-loop Stop, Emergency stop cancellation of active and queued runs, reconnect, signed-out API denial, and turtle fuel/inventory/equipment/peripheral/position data. The server/web/client update is deployed; reboot Computer 14 from the dashboard once so startup downloads the new `client.lua`. Then confirm (a) position displays/copies as `X Y Z` without JSON or clipping, (b) selected slot/equipment refresh immediately after a remote program completes, and (c) peripheral attach/detach refreshes its list. No manual work remains for M0.
