import pytest

from aicontrol.protocol.models import (
    ChunkMessage,
    ConfigMessage,
    ErrorMessage,
    EventMessage,
    ExecMessage,
    ExecResultMessage,
    ExecStartedMessage,
    FsOperationMessage,
    FsResultMessage,
    HeartbeatMessage,
    HelloAckMessage,
    HelloMessage,
    InterruptMessage,
    PeripheralCallMessage,
    PeripheralResultMessage,
    TelemetryMessage,
    TerminalFrameMessage,
    TerminalInputMessage,
    UpdateClientMessage,
)
from aicontrol.protocol.validation import (
    ProtocolPayloadError,
    chunk_message,
    parse_message,
    reassemble_chunks,
)

MESSAGES = [
    HelloMessage(
        type="hello",
        data={
            "device_id": "cc-1",
            "secret": "secret-value",
            "kind": "computer",
            "label": "Test computer",
            "client_version": "0.1.0",
            "capabilities": ["terminal"],
        },
    ),
    HeartbeatMessage(type="heartbeat"),
    TelemetryMessage(type="telemetry", data={"values": {"fuel": 42}}),
    ExecResultMessage(type="exec_result", data={"ok": True, "duration_ms": 1.5}),
    ExecStartedMessage(type="exec_started"),
    EventMessage(type="event", data={"name": "redstone", "args": ["left"]}),
    TerminalFrameMessage(type="term_frame", data={"width": 10, "height": 5, "lines": ["hello"]}),
    FsResultMessage(type="fs_result", data={"operation_id": "fs-1", "path": "/startup", "ok": True}),
    PeripheralResultMessage(
        type="peripheral_result", data={"name": "left", "method": "getItemDetail", "ok": True}
    ),
    HelloAckMessage(type="hello_ack", data={"accept": True, "session_id": "session-1"}),
    ExecMessage(type="exec", id="exec-1", data={"code": "print('hi')"}),
    InterruptMessage(type="interrupt"),
    UpdateClientMessage(type="update_client", data={"version": "0.2.0", "url": "https://example.test/client.lua"}),
    FsOperationMessage(
        type="fs_op", id="fs-op-1", data={"operation_id": "fs-1", "operation": "list", "path": "/"}
    ),
    PeripheralCallMessage(
        type="peripheral_call", id="peripheral-1", data={"name": "left", "method": "getItemDetail"}
    ),
    TerminalInputMessage(type="term_input", data={"text": "help"}),
    ConfigMessage(type="config", data={"settings": {"heartbeat": 30}}),
    ErrorMessage(type="error", data={"code": "denied", "message": "Not paired"}),
    ChunkMessage(
        type="chunk",
        id="chunk-1",
        chunk={"index": 0, "total": 1},
        data={"message_type": "event", "payload": "{}"},
    ),
]


@pytest.mark.parametrize("message", MESSAGES, ids=lambda message: message.type)
def test_each_protocol_message_round_trips(message) -> None:
    parsed = parse_message(message.model_dump_json(exclude_none=True))

    assert parsed is not None
    assert parsed.model_dump(exclude_none=True) == message.model_dump(exclude_none=True)


def test_unknown_type_is_ignored_and_logged(monkeypatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(
        "aicontrol.protocol.validation.logger.warning",
        lambda _format, message_type: logged.append(message_type),
    )
    parsed = parse_message('{"v":1,"type":"future_message","data":{}}')

    assert parsed is None
    assert logged == ["future_message"]


@pytest.mark.parametrize(
    "payload",
    [
        '{"v":1,"type":"exec_result","reply_to":"run-1","data":{"ok":true,"return_values":{},"output":"","duration_ms":1}}',
        '{"v":1,"type":"exec_result","reply_to":"run-1","data":{"ok":false,"return_values":{},"output":"","error":"intentional failure","traceback":"stack trace","duration_ms":1}}',
    ],
)
def test_exec_result_accepts_cc_tweaked_empty_return_table(payload: str) -> None:
    message = parse_message(payload)

    assert isinstance(message, ExecResultMessage)
    assert message.data.return_values == []


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        '{"v":2,"type":"heartbeat","data":{}}',
        '{"v":1,"type":"exec","id":"x","data":{"code":""}}',
        '{"v":1,"type":"heartbeat","extra":true,"data":{}}',
        '{"v":1,"type":"update_client","data":{"version":"1","url":"u","files":{}}}',
        '{"v":1,"type":"chunk","id":"c","chunk":{"index":2,"total":2},"data":{"message_type":"event","payload":""}}',
    ],
)
def test_invalid_payloads_raise_protocol_error(payload: str) -> None:
    with pytest.raises(ProtocolPayloadError):
        parse_message(payload)


def test_oversize_frame_is_rejected_before_parsing() -> None:
    with pytest.raises(ProtocolPayloadError, match="exceeds"):
        parse_message("x" * 33, max_message_bytes=32)


def test_large_message_chunks_and_reassembles_out_of_order() -> None:
    original = ExecResultMessage(
        type="exec_result",
        id="result-1",
        data={"ok": True, "output": "Turtle 🐢 status\n" * 300, "duration_ms": 13},
    )
    chunks = chunk_message(original, max_message_bytes=1024)

    assert len(chunks) > 1
    assert all(len(chunk.model_dump_json(exclude_none=True).encode("utf-8")) <= 1024 for chunk in chunks)
    assert all(isinstance(chunk, ChunkMessage) for chunk in chunks)
    rebuilt = reassemble_chunks(list(reversed(chunks)))

    assert rebuilt == original


def test_chunk_reassembly_rejects_missing_and_duplicate_parts() -> None:
    message = ExecResultMessage(type="exec_result", id="large", data={"ok": True, "output": "x" * 5000, "duration_ms": 0})
    chunks = chunk_message(message, max_message_bytes=512)
    typed_chunks = [chunk for chunk in chunks if isinstance(chunk, ChunkMessage)]

    with pytest.raises(ProtocolPayloadError, match="missing"):
        reassemble_chunks(typed_chunks[:-1])
    with pytest.raises(ProtocolPayloadError, match="duplicate"):
        reassemble_chunks([typed_chunks[0], typed_chunks[0], *typed_chunks[1:]])


def test_invalid_message_envelope_cannot_bypass_typed_union() -> None:
    with pytest.raises(ProtocolPayloadError):
        parse_message('{"v":1,"type":"exec","id":"x","data":{"code":"print(1)","unknown":true}}')
