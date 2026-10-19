import asyncio
import logging
import secrets
import uuid
from typing import Annotated

from anyio import CancelScope
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.db.models import (
    Computer,
    ComputerKind,
    ComputerStatus,
    PairingCode,
    utc_now,
)
from aicontrol.db.security import hash_pairing_code, hash_secret, verify_secret
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
    logger.info("Computer %s marked offline", computer_id)
    await gateway.event_bus.publish(GatewayEvent("offline", computer_id))


async def _authenticate_or_pair(
    session: AsyncSession,
    gateway: WebSocketGateway,
    hello: HelloMessage,
) -> tuple[Computer | None, str | None]:
    computer = await session.get(Computer, hello.data.device_id)
    if computer is not None:
        kind_matches = str(computer.kind) == hello.data.kind
        secret_matches = bool(
            computer.device_secret_hash
            and await asyncio.to_thread(
                verify_secret, computer.device_secret_hash, hello.data.secret
            )
        )
        if kind_matches and secret_matches:
            return computer, None
        logger.warning(
            "Rejected credentials for known computer id=%s (kind_matches=%s, secret_matches=%s)",
            computer.id,
            kind_matches,
            secret_matches,
        )
        return None, None

    code_digest = hash_pairing_code(hello.data.secret)
    async with gateway.pairing_lock:
        pairing_code = await session.scalar(
            select(PairingCode).where(
                PairingCode.code_hash == code_digest,
                PairingCode.used_at.is_(None),
                PairingCode.expires_at > utc_now(),
            )
        )
        if pairing_code is None:
            return None, None
        if (pairing_code.owner_user_id is None) == (pairing_code.owner_team_id is None):
            return None, None

        device_secret = secrets.token_urlsafe(32)
        computer = Computer(
            id=hello.data.device_id,
            owner_user_id=pairing_code.owner_user_id,
            owner_team_id=pairing_code.owner_team_id,
            label=hello.data.label,
            kind=ComputerKind(hello.data.kind),
            cc_version=hello.data.cc_version,
            device_secret_hash=await asyncio.to_thread(hash_secret, device_secret),
        )
        pairing_code.used_at = utc_now()
        session.add(computer)
        await session.commit()
        return computer, device_secret


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

    computer, issued_device_secret = await _authenticate_or_pair(
        session,
        gateway,
        first_message,
    )
    if computer is None:
        known_device = await session.get(Computer, first_message.data.device_id) is not None
        logger.warning(
            "Rejected hello for %s device id (id=%s)",
            "known with invalid secret/kind" if known_device else "unknown or invalid pairing code",
            first_message.data.device_id,
        )
        await _close(websocket, 4401, "invalid device credentials")
        return

    if first_message.data.cc_version:
        computer.cc_version = first_message.data.cc_version
    computer.label = first_message.data.label
    await _set_online(session, computer)
    logger.info("Computer %s authenticated; opening gateway session", computer.id)

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
                    "device_secret": issued_device_secret,
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
                logger.info("Computer %s heartbeat deadline elapsed", computer.id)
                await _set_offline(session, computer.id, gateway)
                offline_marked = True
                await connection.close(4408, "heartbeat timed out")
                break
            try:
                text = await asyncio.wait_for(_receive_text(websocket), timeout=deadline)
            except TimeoutError:
                logger.info("Computer %s missed heartbeat timeout", computer.id)
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
                logger.debug("Heartbeat received from computer %s", computer.id)
            try:
                await connection.receive(message, gateway.event_bus, session)
            except ProtocolPayloadError as exc:
                await connection.close(4400, str(exc))
                break
    except WebSocketDisconnect:
        logger.info("Computer %s WebSocket disconnected", computer.id)
        pass
    finally:
        with CancelScope(shield=True):
            if await gateway.registry.unregister(computer.id, connection) and not offline_marked:
                await _set_offline(session, computer.id, gateway)
            connection.closed = True
