# Development setup

## Prerequisites

- Python 3.12
- Node.js 22 or newer with npm
- Docker with the Compose plugin (for the container workflow)

## Run the backend

From `vibing/ai-control/server`, create and activate a virtual environment, then install the package and development dependencies:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

From `vibing/ai-control`, copy `.env.example` to `.env`, then run `uvicorn aicontrol.main:app --app-dir server/src --reload --host 0.0.0.0 --port 8000`. The API health endpoint is at `http://localhost:8000/api/health`.

The `.env.example` file documents all supported settings, including database and provider-key encryption configuration, web/client distribution directories, the 128 KiB WebSocket frame limit, and hello/heartbeat timing limits.

On first visit to `/`, create the first administrator account (minimum 12-character password). If computers were paired using a passwordless temporary owner such as `manual-test-owner`, enter that same username during setup: it is promoted to the login administrator so the already-owned computers remain visible. The UI then provides the authenticated computer dashboard, Add Computer pairing wizard, telemetry view, Lua run/stop controls and execution history. By default, public signup is disabled; set `AIC_ALLOW_SIGNUP=true` only if additional self-service accounts are desired.

## Run the frontend

In another terminal, from `vibing/ai-control/web`, run `npm install` and `npm run dev`. Vite serves the UI and proxies `/api` and `/ws` to the backend. For the production UI, run `npm run build`; the backend serves `web/dist` automatically.

## Test and lint

From `vibing/ai-control/server`, run `pytest` and `ruff check .`.

## Docker Compose

From `vibing/ai-control`, run `docker compose up --build -d`. The container applies Alembic migrations before starting the app, persists SQLite data in the `ai-control-data` volume, and publishes the app on port 8000 by default. Confirm `http://localhost:8000/api/health` returns `{"status":"ok"}`. Use `docker compose down` to stop it without deleting data; do not pass `-v` unless intentionally resetting the database.
