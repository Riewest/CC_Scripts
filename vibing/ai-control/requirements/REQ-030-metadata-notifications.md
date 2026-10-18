# REQ-030 Labels, tags and notifications
Status: todo | Milestone: M5 | Depends: REQ-008

## Goal
Organise computers with tags and notify users of important events.

## Design notes
- Free-form tags and colour labels on computers, filter and search in the dashboard; notes field.
- Notification events: computer offline for N minutes, low fuel, AI approval needed, goal completed/blocked, fleet run finished, error loops.
- Channels: in-app inbox plus browser web push (optional) and outgoing webhook (Discord/Slack compatible JSON). Per-user preferences.
- Rate limiting and de-duplication of repeated notifications.

## Acceptance criteria
- [ ] Tagging and filtering work.
- [ ] In-app notifications for each event type with preferences.
- [ ] Webhook delivery with retry and signed payloads; SSRF protection (block private IPs unless allowlisted).
- [ ] De-duplication prevents floods.

## Test plan
pytest: event triggers, preferences, webhook signing and SSRF checks, de-dup.

## Files touched
`server/aicontrol/notify/**`, `web/src/pages/Inbox.tsx`.
