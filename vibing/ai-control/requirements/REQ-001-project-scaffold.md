# REQ-001 Project scaffold
Status: done | Milestone: M0 | Depends: none

## Goal
A runnable, testable skeleton for server, web and client with Docker.

## Design notes
- `server/`: `pyproject.toml` (FastAPI, uvicorn[standard], SQLAlchemy 2, alembic, pydantic-settings, argon2-cffi, httpx, pytest, pytest-asyncio, ruff). Package `aicontrol` with `main.py` app factory, `config.py` (env-based settings, prefix `AIC_`), `/api/health`.
- `web/`: Vite + React + TS; build output served by FastAPI at `/` with SPA fallback; dev proxy to the API.
- `client/`: placeholder directory for Lua files.
- `docker-compose.yml` with one service, a volume for the SQLite DB, env file example `.env.example`.
- Multi-stage Dockerfile (node build, python runtime).

## Acceptance criteria
- [x] `pytest` runs and passes with a health-check test.
- [x] `ruff check` is clean.
- [x] `npm run build` in `web/` succeeds and the server serves the built UI.
- [x] `docker compose up` starts the app and `/api/health` returns 200.
- [x] `.env.example` documents every setting.
- [x] README in `docs/` explains dev setup.

## Test plan
pytest: health endpoint, settings loading from env.

## Files touched
`server/**`, `web/**`, `client/.gitkeep`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `docs/dev-setup.md`.
