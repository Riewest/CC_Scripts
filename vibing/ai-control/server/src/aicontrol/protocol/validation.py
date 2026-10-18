import json
import logging
import uuid
from typing import Any

from pydantic import ValidationError

from aicontrol.config import get_settings
from aicontrol.protocol.models import (
    ChunkMessage,
    ProtocolMessage,
    protocol_adapter,
)

logger = logging.getLogger(__name__)


class ProtocolPayloadError(ValueError):
    """A malformed or oversized protocol frame received from a peer."""


def parse_message(
    raw_message: str | bytes,
    *,
    max_message_bytes: int | None = None,
) -> ProtocolMessage | None:
    limit = max_message_bytes or get_settings().max_ws_message_bytes
    encoded = raw_message.encode("utf-8") if isinstance(raw_message, str) else raw_message
    if len(encoded) > limit:
        raise ProtocolPayloadError(f"message exceeds configured limit of {limit} bytes")
    try:
        decoded: Any = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolPayloadError("message must be valid UTF-8 JSON") from exc
    if isinstance(decoded, dict) and isinstance(decoded.get("type"), str):
        if decoded["type"] not in protocol_types():
            logger.warning("Ignoring unknown protocol message type: %s", decoded["type"])
            return None
    try:
        return protocol_adapter.validate_python(decoded)
    except ValidationError as exc:
        raise ProtocolPayloadError("message does not match the versioned protocol schema") from exc


def protocol_types() -> frozenset[str]:
    return frozenset(
        {
            "hello",
            "heartbeat",
            "telemetry",
            "exec_result",
            "exec_started",
            "event",
            "term_frame",
            "fs_result",
            "peripheral_result",
            "hello_ack",
            "exec",
            "interrupt",
            "update_client",
            "fs_op",
            "peripheral_call",
            "term_input",
            "config",
            "error",
            "chunk",
        }
    )


def _encoded(message: ProtocolMessage) -> bytes:
    return message.model_dump_json(exclude_none=True).encode("utf-8")


def chunk_message(
    message: ProtocolMessage,
    *,
    max_message_bytes: int | None = None,
) -> list[ProtocolMessage]:
    limit = max_message_bytes or get_settings().max_ws_message_bytes
    serialized = _encoded(message).decode("utf-8")
    if len(serialized.encode("utf-8")) <= limit:
        return [message]
    if isinstance(message, ChunkMessage):
        raise ProtocolPayloadError("cannot split an already chunked message")

    chunk_id = message.id or f"chunk-{uuid.uuid4()}"
    chunk_size = max(1, limit // 2)
    while chunk_size > 0:
        parts = [serialized[offset : offset + chunk_size] for offset in range(0, len(serialized), chunk_size)]
        chunks = [
            ChunkMessage(
                type="chunk",
                id=chunk_id,
                chunk={"index": index, "total": len(parts)},
                data={"message_type": message.type, "payload": part},
            )
            for index, part in enumerate(parts)
        ]
        if all(len(_encoded(chunk)) <= limit for chunk in chunks):
            return chunks
        if chunk_size == 1:
            break
        chunk_size = max(1, chunk_size // 2)
    raise ProtocolPayloadError(f"configured limit of {limit} bytes is too small for a chunk envelope")


def reassemble_chunks(chunks: list[ChunkMessage]) -> ProtocolMessage:
    if not chunks:
        raise ProtocolPayloadError("at least one chunk is required")
    first = chunks[0]
    total = first.chunk.total
    expected_type = first.data.message_type
    by_index: dict[int, str] = {}
    for chunk in chunks:
        if chunk.id != first.id or chunk.chunk.total != total:
            raise ProtocolPayloadError("chunks do not belong to the same message")
        if chunk.data.message_type != expected_type:
            raise ProtocolPayloadError("chunk message types do not match")
        if chunk.chunk.index in by_index:
            raise ProtocolPayloadError("duplicate chunk index")
        by_index[chunk.chunk.index] = chunk.data.payload
    if set(by_index) != set(range(total)):
        raise ProtocolPayloadError("one or more chunks are missing")

    payload = "".join(by_index[index] for index in range(total))
    message = parse_message(payload, max_message_bytes=len(payload.encode("utf-8")))
    if message is None or message.type != expected_type:
        raise ProtocolPayloadError("reassembled message type does not match its chunks")
    return message
