from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import authenticate_websocket
from aicontrol.db.session import get_session

router = APIRouter()


@router.websocket("/ws/ui")
async def ui_websocket(
    websocket: WebSocket,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    user = await authenticate_websocket(websocket, session)
    if user is None:
        await websocket.close(code=4401, reason="Authentication or origin check failed")
        return
    await websocket.accept()
    await websocket.send_json({"type": "ready", "user": user.username})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
