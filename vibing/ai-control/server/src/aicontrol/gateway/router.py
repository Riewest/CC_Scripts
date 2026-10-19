import asyncio
import logging
import secrets
import uuid
from typing import Annotated

from anyio import CancelScope
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.audit import record
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
from aicontrol.pairing.rate_limit import pairing_exchange_limiter
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
    peer_key: str,
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
        pairing_target = computer.id
    else:
        pairing_target = None

    if pairing_exchange_limiter.limited(peer_key):
        logger.warning("Pairing exchange rate limit reached for peer %s", peer_key)
        return None, None
    code_digest = hash_pairing_code(hello.data.secret)
    async with gateway.pairing_lock:
        pairing_candidate = await session.scalar(
            select(PairingCode).where(
                PairingCode.code_hash == code_digest,
                PairingCode.used_at.is_(None),
                PairingCode.expires_at > utc_now(),
                PairingCode.target_computer_id.is_(None)
                if pairing_target is None
                else PairingCode.target_computer_id == pairing_target,
            )
        )
        if pairing_candidate is None:
            pairing_exchange_limiter.record(peer_key)
            return None, None

        claimed = await session.execute(
            update(PairingCode)
            .where(
                PairingCode.id == pairing_candidate.id,
                PairingCode.used_at.is_(None),
                PairingCode.expires_at > utc_now(),
            )
            .values(used_at=utc_now())
            .execution_options(synchronize_session=False)
            .returning(
                PairingCode.owner_user_id,
                PairingCode.owner_team_id,
                PairingCode.target_computer_id,
                PairingCode.label,
            )
        )
        code_details = claimed.one_or_none()
        if code_details is None:
            pairing_exchange_limiter.record(peer_key)
            return None, None

        device_secret = secrets.token_urlsafe(32)
        owner_user_id, owner_team_id, target_computer_id, label = code_details
        if computer is not None:
            if target_computer_id != computer.id:
                await session.rollback()
                pairing_exchange_limiter.record(peer_key)
                return None, None
            computer.device_secret_hash = await asyncio.to_thread(hash_secret, device_secret)
            computer.kind = ComputerKind(hello.data.kind)
            computer.cc_version = hello.data.cc_version or computer.cc_version
            if label:
                computer.label = label
        else:
            if target_computer_id is not None or (owner_user_id is None) == (owner_team_id is None):
                await session.rollback()
                pairing_exchange_limiter.record(peer_key)
                return None, None
            computer = Computer(
                id=hello.data.device_id,
                owner_user_id=owner_user_id,
                owner_team_id=owner_team_id,
                label=label or hello.data.label,
                kind=ComputerKind(hello.data.kind),
                cc_version=hello.data.cc_version,
                device_secret_hash=await asyncio.to_thread(hash_secret, device_secret),
            )
            session.add(computer)
        await session.flush()
        await session.execute(
            update(PairingCode)
            .where(PairingCode.id == pairing_candidate.id)
            .values(paired_computer_id=computer.id)
        )
        await record(
            session,
            action="pairing.accept",
            actor_type="system",
            computer_id=computer.id,
            target_type="computer",
            target_id=computer.id,
            details={"repaired": target_computer_id is not None},
            commit=False,
        )
        await session.commit()
        pairing_exchange_limiter.clear(peer_key)
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
        websocket.client.host if websocket.client else "unknown",
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
    if issued_device_secret is None:
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
