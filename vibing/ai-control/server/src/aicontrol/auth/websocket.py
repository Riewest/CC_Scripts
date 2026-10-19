import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.auth.sessions import SESSION_COOKIE, authenticate_websocket, lookup_session
from aicontrol.db.session import get_session
from aicontrol.gateway.registry import GatewayEvent
from aicontrol.permissions import PermissionRole, accessible_computers

router = APIRouter()
SESSION_REVALIDATE_INTERVAL = 15.0


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
    accessible = await accessible_computers(user, session)
    authorized_ids = {computer.id for computer, role in accessible if role >= PermissionRole.VIEWER}
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
                    timeout=SESSION_REVALIDATE_INTERVAL,
                )
            except asyncio.CancelledError:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            if receive_task in done:
                try:
                    receive_task.result()
                except WebSocketDisconnect:
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    break
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if not done:
                principal = await lookup_session(
                    websocket.cookies.get(SESSION_COOKIE), session
                )
                if principal is None:
                    await websocket.close(code=4401, reason="Session expired or disabled")
                    return
                current_access = await accessible_computers(principal.user, session)
                current_ids = {
                    computer.id
                    for computer, role in current_access
                    if role >= PermissionRole.VIEWER
                }
                if current_ids != authorized_ids:
                    await websocket.close(code=4403, reason="Computer permissions changed; reconnect")
                    return
                continue
            if event_task in done:
                event: GatewayEvent = event_task.result()
                if event.computer_id in authorized_ids:
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
