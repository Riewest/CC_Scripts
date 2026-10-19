from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aicontrol.auth.routes import router as auth_router
from aicontrol.auth.websocket import router as auth_websocket_router
from aicontrol.config import Settings, get_settings
from aicontrol.gateway.registry import WebSocketGateway
from aicontrol.gateway.router import router as gateway_router


def _find_web_dist(settings: Settings) -> Path | None:
    candidates = [settings.web_dist_dir] if settings.web_dist_dir else []
    candidates.extend(
        [
            Path(__file__).resolve().parents[3] / "web" / "dist",
            Path(__file__).resolve().parent / "static",
        ]
    )
    return next(
        (path.resolve() for path in candidates if path and (path / "index.html").is_file()),
        None,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title="AI Control", debug=app_settings.environment == "development")
    app.state.gateway = WebSocketGateway(app_settings)
    app.include_router(gateway_router)
    app.include_router(auth_router)
    app.include_router(auth_websocket_router)
    web_dist = _find_web_dist(app_settings)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if web_dist:
        assets = web_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        if web_dist is None:
            raise HTTPException(
                status_code=404,
                detail="Web UI is not built; see docs/dev-setup.md",
            )
        return FileResponse(web_dist / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/") or web_dist is None:
            raise HTTPException(status_code=404, detail="Not found")
        root = web_dist.resolve()
        requested_file = (root / path).resolve()
        if requested_file.is_relative_to(root) and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(root / "index.html")

    app.state.settings = app_settings
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("aicontrol.main:app", host=settings.host, port=settings.port)
