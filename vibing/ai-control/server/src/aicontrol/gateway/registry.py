import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.config import Settings
from aicontrol.db.models import AuditEvent
from aicontrol.protocol.models import (
    ChunkMessage,
    ErrorMessage,
    EventMessage,
    ExecResultMessage,
    FsResultMessage,
    HeartbeatMessage,
    PeripheralResultMessage,
    ProtocolMessage,
    TelemetryMessage,
    TerminalFrameMessage,
)
from aicontrol.protocol.validation import ProtocolPayloadError, chunk_message, reassemble_chunks

logger = logging.getLogger(__name__)
CLIENT_MESSAGE_TYPES = (
    HeartbeatMessage,
    TelemetryMessage,
    ExecResultMessage,
    EventMessage,
    TerminalFrameMessage,
    FsResultMessage,
    PeripheralResultMessage,
    ErrorMessage,
    ChunkMessage,
)


@dataclass(frozen=True)
class GatewayEvent:
    name: str
    computer_id: str
    message: ProtocolMessage | None = None
    details: dict[str, Any] | None = None


class EventBus:
    def __init__(self, subscriber_queue_size: int = 256) -> None:
        self._subscribers: set[asyncio.Queue[GatewayEvent]] = set()
        self._subscriber_queue_size = subscriber_queue_size

    def subscribe(self) -> asyncio.Queue[GatewayEvent]:
        queue: asyncio.Queue[GatewayEvent] = asyncio.Queue(maxsize=self._subscriber_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[GatewayEvent]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: GatewayEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)


class GatewayConnection:
    def __init__(self, computer_id: str, websocket: WebSocket, settings: Settings) -> None:
        self.computer_id = computer_id
        self.websocket = websocket
        self.settings = settings
        self.pending: dict[str, asyncio.Future[ProtocolMessage]] = {}
        self._pending_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        self._chunk_sets: dict[str, list[ChunkMessage]] = {}
        self.closed = False

    async def send(self, message: ProtocolMessage) -> None:
        chunks = chunk_message(message, max_message_bytes=self.settings.max_ws_message_bytes)
        async with self._send_lock:
            for item in chunks:
                await self.websocket.send_text(item.model_dump_json(exclude_none=True))

    async def call(self, message: ProtocolMessage, timeout: float) -> ProtocolMessage:
        request_id = message.id
        if not request_id:
            raise ValueError("correlated gateway calls require an envelope id")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        future = asyncio.get_running_loop().create_future()
        async with self._pending_lock:
            if request_id in self.pending:
                raise ValueError(f"request id {request_id!r} is already pending")
            if self.closed:
                raise ConnectionError("computer connection is closed")
            self.pending[request_id] = future
        try:
            await self.send(message)
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            async with self._pending_lock:
                if self.pending.get(request_id) is future:
                    self.pending.pop(request_id, None)
            if not future.done():
                future.cancel()

    async def receive(
        self,
        message: ProtocolMessage,
        event_bus: EventBus,
        session: AsyncSession,
    ) -> None:
        if isinstance(message, ChunkMessage):
            await self._receive_chunk(message, event_bus, session)
            return
        await self._dispatch(message, event_bus, session)

    async def _receive_chunk(
        self,
        chunk: ChunkMessage,
        event_bus: EventBus,
        session: AsyncSession,
    ) -> None:
        if chunk.chunk.total > 1024:
            raise ProtocolPayloadError("chunk set exceeds the 1024-part safety limit")
        if chunk.id not in self._chunk_sets and len(self._chunk_sets) >= 32:
            raise ProtocolPayloadError("too many incomplete chunk sets")
        parts = self._chunk_sets.setdefault(chunk.id, [])
        if any(item.chunk.index == chunk.chunk.index for item in parts):
            raise ProtocolPayloadError("duplicate chunk index")
        if parts and (
            parts[0].chunk.total != chunk.chunk.total
            or parts[0].data.message_type != chunk.data.message_type
        ):
            self._chunk_sets.pop(chunk.id, None)
            raise ProtocolPayloadError("inconsistent chunk set metadata")
        parts.append(chunk)
        if len(parts) == chunk.chunk.total:
            self._chunk_sets.pop(chunk.id, None)
            message = reassemble_chunks(parts)
            if not isinstance(message, CLIENT_MESSAGE_TYPES[:-1]):
                raise ProtocolPayloadError("reassembled message type is not valid in the client direction")
            await self._dispatch(message, event_bus, session)

    async def _dispatch(
        self,
        message: ProtocolMessage,
        event_bus: EventBus,
        session: AsyncSession,
    ) -> None:
        if message.reply_to:
            future = self.pending.get(message.reply_to)
            if future is not None and not future.done():
                future.set_result(message)

        event_name = {
            "telemetry": "telemetry",
            "exec_result": "exec_result",
            "event": "event",
            "term_frame": "term_frame",
            "error": "error",
        }.get(message.type)
        if isinstance(message, ErrorMessage):
            error_details = {
                "code": message.data.code,
                "message": message.data.message,
                "details": message.data.details,
            }
            session.add(
                AuditEvent(
                    action="client_error",
                    target_type="computer",
                    target_id=self.computer_id,
                    details=error_details,
                )
            )
            await session.commit()
            await event_bus.publish(
                GatewayEvent("error", self.computer_id, message, error_details)
            )
        elif event_name:
            await event_bus.publish(GatewayEvent(event_name, self.computer_id, message))

    async def close(self, code: int, reason: str) -> None:
        self.closed = True
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ConnectionError(reason))
        try:
            await self.websocket.close(code=code, reason=reason)
        except (RuntimeError, OSError):
            logger.debug("WebSocket already closed for computer %s", self.computer_id)


class ConnectionRegistry:
    def __init__(self, settings: Settings, event_bus: EventBus | None = None) -> None:
        self.settings = settings
        self.event_bus = event_bus or EventBus()
        self._connections: dict[str, GatewayConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, computer_id: str, connection: GatewayConnection) -> None:
        async with self._lock:
            replaced = self._connections.get(computer_id)
            self._connections[computer_id] = connection
        if replaced is not None and replaced is not connection:
            await replaced.close(4001, "Replaced by a newer connection")

    async def unregister(self, computer_id: str, connection: GatewayConnection) -> bool:
        async with self._lock:
            if self._connections.get(computer_id) is not connection:
                return False
            self._connections.pop(computer_id)
            return True

    async def get(self, computer_id: str) -> GatewayConnection | None:
        async with self._lock:
            return self._connections.get(computer_id)

    async def call(self, computer_id: str, message: ProtocolMessage, timeout: float) -> ProtocolMessage:
        connection = await self.get(computer_id)
        if connection is None:
            raise ConnectionError(f"computer {computer_id!r} is offline")
        return await connection.call(message, timeout)

    async def interrupt(self, computer_id: str, message: ProtocolMessage) -> None:
        connection = await self.get(computer_id)
        if connection is None:
            raise ConnectionError(f"computer {computer_id!r} is offline")
        await connection.send(message)


class WebSocketGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.event_bus = EventBus()
        self.registry = ConnectionRegistry(settings, self.event_bus)
        self.pairing_lock = asyncio.Lock()
