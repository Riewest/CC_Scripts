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

The `.env.example` file documents all supported settings, including database and provider-key encryption configuration, the 128 KiB WebSocket frame limit, and hello/heartbeat timing limits.

## Run the frontend

In another terminal, from `vibing/ai-control/web`, run `npm install` and `npm run dev`. Vite serves the UI and proxies `/api` and `/ws` to the backend. For the production UI, run `npm run build`; the backend serves `web/dist` automatically.

## Test and lint

From `vibing/ai-control/server`, run `pytest` and `ruff check .`.

## Docker Compose

From `vibing/ai-control`, create `.env` from `.env.example`, then run `docker compose up --build`. Compose persists SQLite data in the `ai-control-data` volume and publishes the app on port 8000 by default. Confirm `http://localhost:8000/api/health` returns `{"status":"ok"}`.
