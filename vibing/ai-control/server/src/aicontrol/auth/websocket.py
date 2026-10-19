import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import authenticate_websocket
from aicontrol.db.models import Computer
from aicontrol.db.session import get_session
from aicontrol.gateway.registry import GatewayEvent

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
    event_bus = websocket.app.state.gateway.event_bus
    queue = event_bus.subscribe()
    try:
        while True:
            event_task = asyncio.create_task(queue.get())
            receive_task = asyncio.create_task(websocket.receive_text())
            tasks = {event_task, receive_task}
            try:
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except asyncio.CancelledError:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if receive_task in done:
                receive_task.result()
            if event_task in done:
                event: GatewayEvent = event_task.result()
                computer = await session.get(Computer, event.computer_id)
                if computer is not None and computer.owner_user_id == user.id:
                    payload = {
                        "type": event.name,
                        "computer_id": event.computer_id,
                        "details": event.details,
                    }
                    if event.message is not None:
                        payload["message"] = event.message.model_dump(mode="json", exclude_none=True)
                    await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)
