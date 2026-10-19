# REQ-005 Lua client and installer
Status: blocked | Milestone: M1 | Depends: REQ-003, REQ-004

## Goal
A Lua client that installs with one command, stays connected, runs server-sent code, can be interrupted, and reports all errors.

## Design notes
- Served by the server: `GET /install` returns an installer script; `GET /client/manifest.json` lists files with hashes; `GET /client/<file>`.
- Installer (`wget run https://host/install?code=ABC123` style, exact form defined with REQ-007): downloads client files, writes `/aicontrol/config` (server URL, pairing code), writes `startup.lua`, reboots.
- `startup.lua` checks the manifest on boot and self-updates files, then starts the client; `update_client` message also triggers an update.
- Pairing: first connect uses the pairing code in `hello`; server replies with a device secret persisted in `/aicontrol/config`; later connects use the secret.
- Runner: executes code with `load(code, "=remote", "t", env)` in a coroutine; the main loop uses `parallel.waitForAny` over the WebSocket reader and the running program so an `interrupt` message terminates the program coroutine. Captures `print`/`write` output and return values; sends `exec_result` with error message plus traceback via `xpcall` and `debug.traceback`.
- Program environment is a copy of `_ENV` with `print` redirected to the capture buffer (and the real terminal).
- Telemetry on connect and every N seconds: id, label, kind, advanced, version, uptime, day/time; turtle fuel, fuel limit, selected slot, inventory (16 slots with item details), equipped tools; list of attached peripherals with types; position via INS if `/squid/INS.lua` exists, otherwise GPS if available.
- Reconnect with exponential backoff; never crash the main loop; log to `/aicontrol/log`.
- Known limit: an in-flight `turtle.*` call cannot be aborted; interrupt takes effect at the next yield. Document and report this in the interrupt reply.

## Acceptance criteria
- [x] Installer and `startup.lua` work on computer, turtle and pocket computer (manual checklist).
- [x] Client reconnects after server restart and network loss.
- [x] Runtime and compile errors return message and traceback to the server (manually verified through the integrated UI on Computer 15).
- [ ] Interrupt stops a `while true do end` loop within a second (manual) and the fake-client test covers the protocol side.
- [x] Output and return values are captured and returned, truncated at the size limit with a marker (manually verified output plus both return values through the integrated UI).
- [x] Self-update replaces changed files and restarts cleanly (updated client downloaded through the startup manifest, then connected successfully).
- [x] Manifest and file endpoints implemented and tested server-side.

## Test plan
pytest: manifest hashes, install script content, file serving, pairing handshake with fake client. Current in-game setup and reconnect tests are in the manual test addendum below; integrated UI/run/interrupt checks remain in PLAN.md STOP POINT 1 for the completed M1 milestone.

## Files touched
`client/**`, `server/aicontrol/client_dist/**`, `docs/client.md`.

## Manual test addendum (same-host Docker + Minecraft)

**Current canonical checklist:** use [M0/M1 Manual Validation Checklist](../docs/m0-m1-manual-validation.md). The detailed steps below are historical troubleshooting notes for the earlier install/reconnect phase; do not repeat them unless a fresh device install or reconnect failure needs diagnosis.

Use these steps to test the currently available REQ-005 behavior. Run shell commands in Git Bash/WSL on the host. Since Minecraft and Docker run on the same computer, the ComputerCraft client URL is `http://localhost:8000`. The Docker container must be running throughout installation and reconnect checks. It applies Alembic migrations on startup and stores state in the persistent `ai-control-data` volume.

### 1. Start Docker and confirm the endpoints

```sh
cd /c/Users/Chase/Documents/Repos/CC_Scripts/vibing/ai-control
docker compose up -d --build
docker compose ps
curl.exe --fail http://localhost:8000/api/health
curl.exe --fail http://localhost:8000/client/manifest.json
```

Health should return `{"status":"ok"}` and the manifest should list `client.lua` and `startup.lua`. Leave this terminal/container running. If ComputerCraft reports that HTTP is disabled or cannot reach localhost, enable the CC:Tweaked HTTP API and local-host access in the Minecraft server configuration, then restart Minecraft.

### 2. Seed one-use test pairing codes

There is no registration UI yet. The following creates or reuses an admin test owner, creates three one-use codes valid for 15 minutes, and prints them. Keep the codes private and use each only once.

```sh
docker compose exec -T ai-control python - <<'PY'
import asyncio
import secrets
from datetime import timedelta
from sqlalchemy import select
from aicontrol.db.models import PairingCode, User, UserRole, utc_now
from aicontrol.db.security import hash_pairing_code
from aicontrol.db.session import SessionFactory

async def main():
	async with SessionFactory() as session:
		username = "manual-test-owner"
		owner = await session.scalar(select(User).where(User.username == username))
		if owner is None:
			owner = User(username=username, role=UserRole.ADMIN)
			session.add(owner)
			await session.flush()

		codes = {
			kind: secrets.token_urlsafe(12)
			for kind in ("computer", "turtle", "pocket")
		}
		for code in codes.values():
			session.add(PairingCode(
				code_hash=hash_pairing_code(code),
				owner_user_id=owner.id,
				expires_at=utc_now() + timedelta(minutes=15),
			))
		await session.commit()
		for kind, code in codes.items():
			print(f"{kind.upper()}_PAIRING_CODE={code}")

asyncio.run(main())
PY
```

### 3. Install and pair a fresh device of each kind

Run the matching command in the ComputerCraft shell for each fresh device. Replace the code placeholder with the printed value. The installer downloads the manifest/files, creates `/aicontrol/config`, installs `/startup.lua` and `/aicontrol/client.lua`, then reboots.

Normal computer:

```text
wget run http://localhost:8000/install?code=PASTE_COMPUTER_PAIRING_CODE
```

Turtle:

```text
wget run http://localhost:8000/install?code=PASTE_TURTLE_PAIRING_CODE
```

Pocket computer:

```text
wget run http://localhost:8000/install?code=PASTE_POCKET_PAIRING_CODE
```

Wait for each reboot/startup to finish. In each computer shell, `ls /aicontrol` should show `client.lua` and `config`. Do not display or share `/aicontrol/config`; it contains the persistent device secret. On first successful pairing the server consumes the pairing code and returns a new random device secret for the client to save.

If the shell still appears occupied after `wget run`, do not run the installer again. Once installed, `startup.lua` launches the always-on client in the foreground, so the device shell being occupied is expected. The Docker access log shows that HTTP downloads completed, while repeated `/ws/computer` connections indicate the client is retrying rather than staying connected.

To stop one retrying device and get a safe diagnostic:

1. On that device only, press **Ctrl+T**. If it retries instead of returning to the shell, press **Ctrl+T** once more during the retry delay.
2. At the shell prompt, run:

	```text
	type /aicontrol/log
	```

3. Copy the log output. Do **not** run `type /aicontrol/config`, and do not reinstall yet: the pairing code has likely already been consumed.
4. Optionally rerun the safe database status command from step 4. The paired row existing confirms pairing completed; an `offline` status only means the client did not maintain its session.
5. Share the `/aicontrol/log` output and the safe status rows (label, kind, status, last-seen only) so the reconnect failure can be diagnosed before continuing with the other devices.

Interpretation: `fatal client error: Terminated` is expected when Ctrl+T terminates the client; by itself it does not explain the earlier reconnects. The later pocket log reports `invalid device credentials`. That is expected for the prior `code=refresh` attempt: the installer generated a **new device ID**, and `refresh` is not a valid one-time pairing code. The database's old device row cannot authenticate that new ID, so the server rejects it. The initial three device IDs/records are separate and the new pocket install did not repair or alter them.

The client now says `server closed before hello acknowledgement` rather than incorrectly calling a server rejection a timeout. The gateway also logs whether a hello used an unknown device ID or had an invalid secret/kind, without logging the secret. Rebuild the service once before retrying to get these diagnostics:

```sh
docker compose up -d --build
curl.exe --fail http://localhost:8000/api/health
```

If a fresh log instead says `server accepted hello`, then `websocket reader ended: Timed out`, pairing succeeded. CC:Tweaked's `Websocket.receive(timeout)` uses the reason text `Timed out`; the client must treat this as normal polling, not terminate the reader. The client recognizes both `timeout` and `timed out` spellings, leaving the heartbeat worker active.

If that log was produced before the latest rebuild, stop the retrying client with Ctrl+T and run `reboot` from its shell. Startup compares the installed files with the now-updated server manifest and replaces `client.lua`; the existing device ID and saved device secret remain unchanged. Do **not** reinstall or consume another pairing code for this fix. After reboot, the log should show `server accepted hello` without a subsequent `websocket reader ended: Timed out`; the device should stay online and refresh `last_seen` as heartbeats arrive.

Only if the log still says `invalid device credentials` after the client refresh, create a **new valid pairing code** for a fresh installation. This is a one-use code, valid for 15 minutes. Do not do this for the `Timed out` case above; the existing pairing is valid.

```sh
docker compose exec -T ai-control python - <<'PY'
import asyncio
import secrets
from datetime import timedelta
from sqlalchemy import select
from aicontrol.db.models import PairingCode, User, utc_now
from aicontrol.db.security import hash_pairing_code
from aicontrol.db.session import SessionFactory

async def main():
	async with SessionFactory() as session:
		owner = await session.scalar(
			select(User).where(User.username == "manual-test-owner")
		)
		if owner is None:
			raise RuntimeError("manual-test-owner is missing; rerun the original step 2 seed command")
		code = secrets.token_urlsafe(12)
		session.add(PairingCode(
			code_hash=hash_pairing_code(code),
			owner_user_id=owner.id,
			expires_at=utc_now() + timedelta(minutes=15),
		))
		await session.commit()
		print("NEW_PAIRING_CODE=" + code)

asyncio.run(main())
PY
```

On the pocket, press Ctrl+T until the shell returns. Then install again using the newly printed value (not the literal word `refresh`):

```text
wget run http://localhost:8000/install?code=PASTE_NEW_PAIRING_CODE
```

This creates yet another new device ID. Once it reboots, use step 4's safe status query. If it still fails, run `type /aicontrol/log` **before pressing Ctrl+T** and share the new entries, plus server logs from `docker compose logs --since=2m ai-control`. Do not share `/aicontrol/config`, pairing codes, or device secrets. Do not reinstall the original computer/turtle with placeholder codes; their saved configs contain their original device secrets.

### 4. Check which computers are online

Run this in Git Bash. It prints only labels, kinds, status, and last-seen timestamps, never hashes or secrets.

```sh
docker compose exec -T ai-control python - <<'PY'
import asyncio
from sqlalchemy import select
from aicontrol.db.models import Computer
from aicontrol.db.session import SessionFactory

async def main():
	async with SessionFactory() as session:
		computers = await session.scalars(select(Computer).order_by(Computer.label))
		for computer in computers:
			print(computer.label, computer.kind, computer.status, computer.last_seen)

asyncio.run(main())
PY
```

Each connected device should report `online`. Reboot each device with its in-game `reboot` command and rerun the query. It should reconnect using its saved device secret even though its one-use pairing code has already been consumed.

### 5. Verify server restart and brief network outage recovery

Restart the app while leaving Minecraft and its computers running:

```sh
docker compose restart ai-control
docker compose logs -f ai-control
```

Use Ctrl+C to exit the log stream; this does not stop the container. The clients should reconnect. Rerun the query from step 4 and verify they return to `online`.

To simulate a short outage instead:

```sh
docker compose stop ai-control
docker compose start ai-control
```

Again verify the devices return to `online`. When all available checks are finished, stop the stack without deleting the persisted database:

```sh
docker compose down
```

Do not use `docker compose down -v`; `-v` deletes the database volume and the paired device records.

### 6. Record what this requirement can and cannot verify today

- [x] Fresh install/pairing and stable online status verified on the pocket computer after the receive-timeout fix.
- [x] Fresh install and pairing on a normal computer and turtle; both return online.
- [x] Pocket reboot reconnects using its saved device secret; `last_seen` advanced while online.
- [x] Verify normal computer and turtle reboot reconnect using their saved device secrets.
- [x] Docker restart and short stop/start outage are recovered; devices return online.
- [ ] Real remote code output/return values, compile/runtime traceback display, and one-second `while true do end` interrupt. **Blocked:** the current scaffold has no run-code/interrupt UI or API.
- [ ] Visible turtle telemetry, pocket terminal control, and interactive self-update. **Blocked:** their UI/API is not part of REQ-005; these are delivered by later operator-tool requirements.

Do not mark the blocked checks as passed based only on Lua syntax parsing or automated fake-client tests. Carry the remaining UI-dependent checks to the relevant requirements and revisit them at the full MVP milestone stop point.
