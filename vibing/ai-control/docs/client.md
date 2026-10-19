# CC:Tweaked client

The client targets CC:Tweaked 1.120.0 and uses only built-in APIs. It runs on computers, turtles, and pocket computers.

## Install and pair

Create a one-time pairing code in the web application (pair-code creation is added by the registration-flow requirement), then run the generated command in the computer's shell:

```text
wget run https://your-host/install?code=YOUR_PAIRING_CODE
```

For a local/LAN development server, use its reachable `http://host:8000` address. The installer downloads the SHA-256 manifest and its files, writes `/aicontrol/config`, installs `/startup.lua` and `/aicontrol/client.lua`, then reboots. The config includes the server URL, a generated client ID, and the one-time pairing code.

On first connection, the client places that code in the `hello` secret field. The server consumes the code once, creates the computer record, returns a new random device secret in `hello_ack.data.device_secret`, and the client persists that secret while clearing the pairing code. Later connections authenticate with the device secret. Never share `/aicontrol/config` or paste its secret into a URL.

The installer endpoint is `GET /install?code=...`; `GET /client/manifest.json` returns the version and SHA-256 hashes, and `GET /client/<name>` serves only listed client files. `startup.lua` checks the manifest on each boot, downloads file contents, and replaces only changed files. Server-side hashes are also covered by the automated manifest tests.

## Runtime behavior

- The client reconnects with exponential backoff (1, 2, 4, ... up to 60 seconds), resets the delay to one second after a successful session, and logs failures to `/aicontrol/log`.
- It sends heartbeats and periodic telemetry. It also sends a fresh snapshot after each remote program completes and immediately when a peripheral attaches or detaches. Turtle telemetry includes fuel, selected slot, inventory details and equipped tools. It reports peripherals and reads `/GPS/INS.json` when `/squid/INS.lua` is present; otherwise it tries GPS when available.
- Remote code runs in a copied global environment. `print` and `write` output is captured and also shown on the computer. Return values are converted to dense JSON arrays; nil, non-finite numbers and cyclic tables use explicit JSON-safe representations. Large results are truncated with a marker before transmission.
- The executor checks for an interrupt every 10,000 Lua instructions using a coroutine debug hook. A pending turtle/peripheral API call is not preemptible; the interrupt is applied at the next Lua yield and the client replies with this limitation. This behavior was verified on the M1 target build.
- A server `update_client` message applies supplied files, or accepts a URL to a JSON manifest shaped as `{"version":"...","files":{"client.lua":"https://.../client.lua"}}`; downloaded files are installed and the client reboots so new startup/client code runs cleanly.

## Validation history

The completed M0/M1 manual acceptance results are retained in the [archived validation record](../requirements/manual-validation/M0-M1-validation-record.md). For installation and daily operation, use the instructions above.
