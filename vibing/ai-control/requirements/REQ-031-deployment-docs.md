# REQ-031 Deployment and transport docs
Status: todo | Milestone: M6 | Depends: all

## Goal
Documented, tested deployment paths for LAN/localhost and public TLS.

## Design notes
- `docs/deployment.md` covering:
  - Docker compose quickstart, volumes, backups, upgrading and migrations.
  - LAN/localhost: CC:Tweaked blocks private/local addresses by default; show editing `config/computercraft-server.toml` (`[[http.rules]]` allow host/port, `websocket_enabled`, `max_websocket_message`) for singleplayer (`saves/<world>/serverconfig`) and servers; give a verified example for the 1.120.0 config.
  - Public: reverse proxy (Caddy and nginx examples) with TLS and WebSocket upgrade, `wss://` URL in `AIC_PUBLIC_URL`, trusted proxy headers, origin checks.
  - Postgres switch instructions.
- Health/readiness endpoints, structured logging, example env file complete.
- Verify config key names against the CC:Tweaked 1.120.0 source at the tag in PLAN.md.

## Acceptance criteria
- [ ] Both transport modes documented step by step and checked against the real config.
- [ ] Compose file production-ready (non-root user, healthcheck, restart policy).
- [ ] Proxy examples tested for WebSocket upgrade.
- [ ] Backup and restore documented.

## Test plan
Manual verification of each doc path; pytest for health endpoints and proxy-header handling.

## Files touched
`docs/deployment.md`, `docker-compose.yml`, `Dockerfile`, `docs/proxy/*`.
