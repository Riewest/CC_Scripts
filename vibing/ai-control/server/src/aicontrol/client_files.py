import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse

from aicontrol.config import Settings

router = APIRouter()
CLIENT_VERSION = "0.1.0"
INSTALLER_TEMPLATE = "install.lua.template"


def find_client_dist(settings: Settings) -> Path | None:
    candidates = [settings.client_dist_dir] if settings.client_dist_dir else []
    candidates.extend([
        Path(__file__).resolve().parents[3] / "client",
        Path(__file__).resolve().parent / "client_dist",
    ])
    return next((path.resolve() for path in candidates if (path / "startup.lua").is_file()), None)


def client_manifest(directory: Path) -> dict[str, object]:
    files = {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != INSTALLER_TEMPLATE and path.name != ".gitkeep"
    }
    return {"version": CLIENT_VERSION, "algorithm": "sha256", "files": files}


def _lua_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


@router.get("/install", response_class=PlainTextResponse, include_in_schema=False)
async def installer(request: Request, code: str = Query(min_length=1, max_length=128)) -> PlainTextResponse:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", code):
        raise HTTPException(status_code=400, detail="Invalid pairing code format")
    directory = find_client_dist(request.app.state.settings)
    if directory is None:
        raise HTTPException(status_code=404, detail="Client files are not installed")
    template_path = directory / INSTALLER_TEMPLATE
    if not template_path.is_file():
        raise HTTPException(status_code=404, detail="Installer template is missing")
    template = template_path.read_text(encoding="utf-8")
    script = template.replace("__SERVER_URL__", _lua_string(str(request.base_url).rstrip("/")))
    script = script.replace("__PAIRING_CODE__", _lua_string(code))
    return PlainTextResponse(script, media_type="text/plain; charset=utf-8")


@router.get("/client/manifest.json", include_in_schema=False)
async def manifest(request: Request) -> dict[str, object]:
    directory = find_client_dist(request.app.state.settings)
    if directory is None:
        raise HTTPException(status_code=404, detail="Client files are not installed")
    return client_manifest(directory)


@router.get("/client/{file_path:path}", include_in_schema=False)
async def client_file(request: Request, file_path: str) -> FileResponse:
    directory = find_client_dist(request.app.state.settings)
    if directory is None:
        raise HTTPException(status_code=404, detail="Client files are not installed")
    files = client_manifest(directory)["files"]
    if file_path not in files:
        raise HTTPException(status_code=404, detail="Client file not found")
    path = (directory / file_path).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        raise HTTPException(status_code=404, detail="Client file not found")
    return FileResponse(path)
