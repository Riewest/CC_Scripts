# AI Control wire protocol (v1)

Client and server exchange UTF-8 JSON **text** WebSocket frames. Each complete message has this envelope:

```json
{"v":1,"type":"heartbeat","id":"optional-request-id","reply_to":"optional-request-id","data":{}}
```

- `v` is the protocol version. This release accepts only integer `1`.
- `type` selects a validated message schema. Unknown message types are ignored and logged by the server; malformed JSON, unsupported versions, unknown fields, and invalid payloads are rejected as protocol payload errors. The WebSocket handler should close or return an error for these errors rather than letting a validation exception escape its task.
- `id` identifies a request or message; `reply_to` correlates a response. They are optional unless a message below says otherwise.
- `data` contains the message-specific fields. Extra fields are rejected so incompatible clients fail clearly.
- A secret is sent only in the `hello` data over the WebSocket; **never put it in a URL or query string**. Use `wss://` over untrusted networks.

JSON values in the examples are illustrative. Fields called optional may be omitted or `null` unless stated. The server's Pydantic schema is authoritative for field types and bounds.

## Client → server messages

| Type | Data | Purpose |
|---|---|---|
| `hello` | `device_id` string, `secret` string, `kind` (`computer`, `turtle`, or `pocket`), `label` string, `client_version` string; optional `cc_version` string and `capabilities` string array | Authenticate and identify a client at connection start. |
| `heartbeat` | Optional `timestamp` string and nonnegative `sequence` integer | Keep the connection alive and report liveness. |
| `telemetry` | `values` object; optional `timestamp` string | Report extensible device metrics. |
| `exec_result` | `ok` boolean, `duration_ms` nonnegative number; optional `return_values` JSON array, `output` string, `error` string, `traceback` string | Return the result and captured output for an execution. `return_values` must be a dense JSON array. |
| `exec_started` | Optional `name` and `started_at` strings | Indicate that a requested execution started. |
| `event` | `name` string and optional `args` JSON array | Forward a CC:Tweaked event. |
| `term_frame` | `width`, `height` positive integers; `lines` string array; optional cursor coordinates and `cursor_blink` boolean | Send a terminal snapshot. Dimensions are limited to 512. |
| `fs_result` | `operation_id`, `path`, `ok`; optional `entries` array, `content`, `error` | Return a filesystem operation result. |
| `peripheral_result` | `name`, `method`, `ok`; optional JSON `result` and `error` | Return a peripheral call result. |

Example client hello:

```json
{"v":1,"type":"hello","id":"connect-17","data":{"device_id":"cc-42","secret":"<device-secret>","kind":"turtle","label":"Quarry 1","cc_version":"1.120.0","client_version":"0.1.0","capabilities":["terminal","filesystem","peripherals"]}}
```

For initial pairing, `hello.data.secret` contains the one-time pairing code. The server consumes it, creates the computer record, and returns a generated `device_secret` in an accepted `hello_ack`; the client stores that secret and uses it for subsequent connections. The code and device secret are never sent in the URL.

## Server → client messages

| Type | Data | Purpose |
|---|---|---|
| `hello_ack` | `accept` boolean; optional `session_id`, `reason`; `heartbeat_interval_s` positive integer (default 30); `max_message_bytes` positive integer (default 131072) | Accept or reject a connection and publish connection limits. |
| `exec` | `code` nonempty string; optional `name` (default `remote`) and positive `timeout_ms` (default 30000); **envelope `id` required** | Run code on a computer. Return `exec_started` and `exec_result` correlated with this ID. |
| `interrupt` | Optional `reason` string | Interrupt the currently running execution. |
| `update_client` | `version` string and exactly one of `files` (filename-to-content object) or `url` string | Install a client update. |
| `fs_op` | `operation_id`, `operation` (`read`, `write`, `list`, `delete`, `mkdir`), `path`; optional `content`; **envelope `id` required** | Request a filesystem operation. |
| `peripheral_call` | `name`, `method`, optional JSON `args` array; **envelope `id` required** | Invoke an exposed peripheral method. |
| `term_input` | `text` string (up to 4096 characters) | Send text to the terminal. |
| `config` | `settings` object | Update client configuration. |
| `error` | `code` and `message` strings; optional `details` object | Report a protocol or operation error. |

Example execution request and reply:

```json
{"v":1,"type":"exec","id":"run-91","data":{"name":"inspect","code":"print(os.getComputerID())","timeout_ms":10000}}
{"v":1,"type":"exec_result","reply_to":"run-91","data":{"ok":true,"return_values":[],"output":"42\n","duration_ms":4.2}}
```

## Frame size and chunking

The default maximum is **131072 bytes (128 KiB) per encoded UTF-8 JSON frame**, configured by `AIC_MAX_WS_MESSAGE_BYTES` and sent to the client in `hello_ack.data.max_message_bytes`. Enforce the limit on received frames before parsing. If an ordinary message fits, send it unchanged. Otherwise split its serialized UTF-8 JSON text into `chunk` envelopes:

```json
{"v":1,"type":"chunk","id":"run-91","chunk":{"index":0,"total":3},"data":{"message_type":"exec_result","payload":"{\"v\":1,\"type\":\"exec_result\",..."}}
```

`chunk.index` is zero-based, `chunk.total` is the number of parts, and every part has the same envelope `id`, `data.message_type`, and `chunk.total`. `data.payload` is a text slice of the original serialized JSON; concatenate slices in index order to recover the original message. Each chunk envelope itself must fit under the same byte limit. Receivers may get chunks out of order; reject duplicates, missing parts, inconsistent IDs/types/totals, or an incomplete set. Bound the number and aggregate bytes of buffered chunks in a future connection handler. The Python `chunk_message` and `reassemble_chunks` helpers enforce frame-size and consistency checks.

## CC:Tweaked JSON interoperability

Use `textutils.serializeJSON` and `textutils.unserializeJSON` for text frames. Their JSON representation cannot safely encode sparse Lua arrays or `NaN`/infinities:

- Make arrays dense. Represent missing array positions explicitly with `json.null` (or a documented tagged object), not a Lua `nil` hole.
- Normalize non-finite numbers before serialization: use `null` when loss is acceptable, or a tagged object such as `{"$number":"nan"}` / `{"$number":"infinity"}` when the receiver must distinguish them.
- Keep object keys as strings and represent binary data with an agreed textual encoding (for example base64) rather than raw bytes.

Unknown message types are forward-compatible and can be ignored; a known type with an invalid payload must not be acted upon. Do not log hello secrets or full message bodies.
