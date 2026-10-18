# REQ-018 Event streaming
Status: todo | Milestone: M3 | Depends: REQ-008

## Goal
Stream selected CC events (redstone, chat, peripheral attach/detach, modem messages, turtle events, custom) to the UI and make them available to AI.

## Design notes
- Client has a background event tap (parallel to the runner) that forwards subscribed event names with args; subscription list set by server (`config`).
- Defaults: `peripheral`, `peripheral_detach`, `redstone`, `chat`/`chat_message` (Advanced Peripherals), `modem_message` (opt-in), `turtle_inventory`, `alarm`, `timer` opt-in.
- Server stores a rolling buffer per computer (size/time-limited) and exposes it to the UI over the UI websocket and to AI as a tool (REQ-022).
- Rate limiting and truncation on the client to avoid flooding.
- UI: event feed with filters and pause.

## Acceptance criteria
- [ ] Subscribed events show live in the UI.
- [ ] Rate limit and payload truncation enforced client-side and server-side.
- [ ] Rolling buffer queryable via API with filters.
- [ ] Event tap never blocks or consumes events needed by running programs.

## Test plan
pytest: subscription config, buffer limits, filtering, flood handling.

## Files touched
`server/aicontrol/events/**`, `client/events.lua`, `web/src/pages/Events.tsx`.
