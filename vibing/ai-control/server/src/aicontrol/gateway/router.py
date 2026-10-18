import asyncio
import logging
import uuid
from typing import Annotated

from anyio import CancelScope
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.db.models import Computer, ComputerStatus, utc_now
from aicontrol.db.security import verify_secret
from aicontrol.db.session import get_session
from aicontrol.gateway.registry import (
    CLIENT_MESSAGE_TYPES,
    GatewayConnection,
    GatewayEvent,
    WebSocketGateway,
)
from aicontrol.protocol.models import (
    HeartbeatMessage,
    HelloAckMessage,
    HelloMessage,
)
from aicontrol.protocol.validation import ProtocolPayloadError, parse_message

logger = logging.getLogger(__name__)
router = APIRouter()


def _gateway(websocket: WebSocket) -> WebSocketGateway:
    return websocket.app.state.gateway


async def _receive_text(websocket: WebSocket) -> str:
    frame = await websocket.receive()
    if frame["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(frame.get("code", 1000), frame.get("reason", ""))
    text = frame.get("text")
    if not isinstance(text, str):
        raise ProtocolPayloadError("only text JSON frames are supported")
    return text


async def _close(websocket: WebSocket, code: int, reason: str) -> None:
    try:
        await websocket.close(code=code, reason=reason)
    except (RuntimeError, OSError):
        logger.debug("WebSocket was already closed")


async def _set_online(session: AsyncSession, computer: Computer) -> None:
    computer.status = ComputerStatus.ONLINE
    computer.last_seen = utc_now()
    await session.commit()


async def _set_offline(session: AsyncSession, computer_id: str, gateway: WebSocketGateway) -> None:
    computer = await session.get(Computer, computer_id)
    if computer is not None:
        computer.status = ComputerStatus.OFFLINE
        await session.commit()
    await gateway.event_bus.publish(GatewayEvent("offline", computer_id))


@router.websocket("/ws/computer")
async def computer_websocket(
    websocket: WebSocket,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    gateway = _gateway(websocket)
    await websocket.accept()
    try:
        first_text = await asyncio.wait_for(
            _receive_text(websocket), timeout=gateway.settings.hello_timeout_s
        )
        first_message = parse_message(
            first_text,
            max_message_bytes=gateway.settings.max_ws_message_bytes,
        )
    except TimeoutError:
        await _close(websocket, 4408, "hello timed out")
        return
    except ProtocolPayloadError as exc:
        code = 4409 if "exceeds" in str(exc) else 4400
        await _close(websocket, code, str(exc))
        return
    except WebSocketDisconnect:
        return

    if not isinstance(first_message, HelloMessage):
        await _close(websocket, 4400, "first message must be hello")
        return

    computer = await session.get(Computer, first_message.data.device_id)
    valid_secret = False
    if computer is not None and computer.device_secret_hash is not None:
        valid_secret = await asyncio.to_thread(
            verify_secret,
            computer.device_secret_hash,
            first_message.data.secret,
        )
    if (
        computer is None
        or computer.device_secret_hash is None
        or not valid_secret
        or str(computer.kind) != first_message.data.kind
    ):
        await _close(websocket, 4401, "invalid device credentials")
        return

    if first_message.data.cc_version:
        computer.cc_version = first_message.data.cc_version
    computer.label = first_message.data.label
    await _set_online(session, computer)

    connection = GatewayConnection(computer.id, websocket, gateway.settings)
    await gateway.registry.register(computer.id, connection)
    await gateway.event_bus.publish(GatewayEvent("online", computer.id))
    offline_marked = False
    try:
        await connection.send(
            HelloAckMessage(
                type="hello_ack",
                reply_to=first_message.id,
                data={
                    "accept": True,
                    "session_id": str(uuid.uuid4()),
                    "heartbeat_interval_s": gateway.settings.heartbeat_interval_s,
                    "max_message_bytes": gateway.settings.max_ws_message_bytes,
                },
            )
        )
        last_heartbeat = asyncio.get_running_loop().time()
        while True:
            deadline = gateway.settings.heartbeat_timeout_s - (
                asyncio.get_running_loop().time() - last_heartbeat
            )
            if deadline <= 0:
                await _set_offline(session, computer.id, gateway)
                offline_marked = True
                await connection.close(4408, "heartbeat timed out")
                break
            try:
                text = await asyncio.wait_for(_receive_text(websocket), timeout=deadline)
            except TimeoutError:
                await _set_offline(session, computer.id, gateway)
                offline_marked = True
                await connection.close(4408, "heartbeat timed out")
                break
            try:
                message = parse_message(
                    text,
                    max_message_bytes=gateway.settings.max_ws_message_bytes,
                )
            except ProtocolPayloadError as exc:
                code = 4409 if "exceeds" in str(exc) else 4400
                await connection.close(code, str(exc))
                break
            if message is None:
                continue
            if not isinstance(message, CLIENT_MESSAGE_TYPES):
                await connection.close(4400, "message type is not valid in the client direction")
                break
            if isinstance(message, HeartbeatMessage):
                last_heartbeat = asyncio.get_running_loop().time()
                computer.last_seen = utc_now()
                computer.status = ComputerStatus.ONLINE
                await session.commit()
            try:
                await connection.receive(message, gateway.event_bus, session)
            except ProtocolPayloadError as exc:
                await connection.close(4400, str(exc))
                break
    except WebSocketDisconnect:
        pass
    finally:
        with CancelScope(shield=True):
            if await gateway.registry.unregister(computer.id, connection) and not offline_marked:
                await _set_offline(session, computer.id, gateway)
            connection.closed = True
