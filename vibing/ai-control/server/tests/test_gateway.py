import asyncio
import threading
import time

import pytest
from fakecc import FakeCC
from fastapi import WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aicontrol.config import Settings
from aicontrol.db.models import AuditEvent, Computer, ComputerStatus
from aicontrol.gateway.registry import GatewayConnection, WebSocketGateway
from aicontrol.protocol.models import ExecMessage, ExecResultMessage, InterruptMessage
from aicontrol.protocol.validation import parse_message


def read_computer_status(database_url: str, computer_id: str) -> tuple[ComputerStatus, object]:
    async def read() -> tuple[ComputerStatus, object]:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            computer = await session.get(Computer, computer_id)
            assert computer is not None
            result = (computer.status, computer.last_seen)
        await engine.dispose()
        return result

    return asyncio.run(read())


def wait_for_unregistered(app, computer_id: str) -> None:
    deadline = time.monotonic() + 2
    while computer_id in app.state.gateway.registry._connections and time.monotonic() < deadline:
        time.sleep(0.005)
    assert computer_id not in app.state.gateway.registry._connections


def test_valid_hello_connects_and_heartbeat_updates_database(gateway_context) -> None:
    client, app, database_url, computer_id = gateway_context
    events = app.state.gateway.event_bus.subscribe()

    with FakeCC(client, computer_id, "correct-secret") as cc:
        ack = cc.receive_json()
        assert ack["type"] == "hello_ack"
        assert ack["data"]["accept"] is True
        assert events.get_nowait().name == "online"

        cc.send_json({"v": 1, "type": "heartbeat", "data": {"sequence": 1}})
        assert read_computer_status(database_url, computer_id)[0] == ComputerStatus.ONLINE
        cc.disconnect()
        wait_for_unregistered(app, computer_id)

    assert events.get_nowait().name == "offline"
    status, last_seen = read_computer_status(database_url, computer_id)
    assert status == ComputerStatus.OFFLINE
    assert last_seen is not None
    app.state.gateway.event_bus.unsubscribe(events)


def test_invalid_device_secret_is_closed_with_reason(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    with client.websocket_connect("/ws/computer") as websocket:
        websocket.send_json(
            {
                "v": 1,
                "type": "hello",
                "data": {
                    "device_id": computer_id,
                    "secret": "incorrect-secret",
                    "kind": "computer",
                    "label": "Fake",
                    "client_version": "test",
                },
            }
        )
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    assert closed.value.code == 4401
    assert "credentials" in closed.value.reason


def test_pairing_code_issues_persistent_device_secret(gateway_context) -> None:
    client, app, database_url, _ = gateway_context
    device_id = "paired-device"
    with FakeCC(client, device_id, "pairing-code") as cc:
        ack = cc.receive_json()
        assert ack["data"]["accept"] is True
        device_secret = ack["data"]["device_secret"]
        assert device_secret
        cc.disconnect()
        wait_for_unregistered(app, device_id)

    with FakeCC(client, device_id, device_secret) as cc:
        ack = cc.receive_json()
        assert ack["data"]["accept"] is True
        assert "device_secret" not in ack["data"]
        cc.disconnect()
        wait_for_unregistered(app, device_id)

    status, _ = read_computer_status(database_url, device_id)
    assert status == ComputerStatus.OFFLINE


def test_missing_hello_is_closed_with_timeout(gateway_context) -> None:
    client, _, _, _ = gateway_context
    with client.websocket_connect("/ws/computer") as websocket:
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    assert closed.value.code == 4408
    assert "hello" in closed.value.reason


def test_duplicate_connection_replaces_old_socket(gateway_context) -> None:
    client, app, database_url, computer_id = gateway_context
    first = FakeCC(client, computer_id, "correct-secret")
    with first:
        assert first.receive_json()["data"]["accept"] is True
        with FakeCC(client, computer_id, "correct-secret") as second:
            assert second.receive_json()["data"]["accept"] is True
            assert computer_id in client.app.state.gateway.registry._connections
            with pytest.raises(WebSocketDisconnect) as replaced:
                first.receive_json()
            assert replaced.value.code == 4001
            second.disconnect()
            wait_for_unregistered(app, computer_id)
    assert read_computer_status(database_url, computer_id)[0] == ComputerStatus.OFFLINE


def test_fake_client_exec_request_round_trip_over_websocket(gateway_context) -> None:
    client, app, _, computer_id = gateway_context
    async def issue_exec():
        return await app.state.gateway.registry.call(
            computer_id,
            ExecMessage(type="exec", id="wire-exec-1", data={"name": "test", "code": "return 42"}),
            timeout=2,
        )

    app.add_api_route("/_test/exec", issue_exec, methods=["POST"])
    results: list[dict] = []
    request_errors: list[BaseException] = []

    def call_from_server() -> None:
        try:
            response = client.post("/_test/exec")
            results.append(response.json())
        except BaseException as exc:
            request_errors.append(exc)

    with FakeCC(client, computer_id, "correct-secret") as cc:
        assert cc.receive_json()["type"] == "hello_ack"
        caller = threading.Thread(target=call_from_server)
        caller.start()
        request = cc.receive_json()
        assert request["type"] == "exec"
        cc.send_json(
            {
                "v": 1,
                "type": "exec_result",
                "reply_to": request["id"],
                "data": {"ok": True, "return_values": [42], "duration_ms": 2},
            }
        )
        caller.join(timeout=3)
        assert not caller.is_alive()
        assert not request_errors
        assert results[0]["type"] == "exec_result"
        assert results[0]["data"]["return_values"] == [42]
        cc.disconnect()
        wait_for_unregistered(app, computer_id)


def test_malformed_and_oversized_frames_close_without_server_error(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    with FakeCC(client, computer_id, "correct-secret") as cc:
        assert cc.receive_json()["type"] == "hello_ack"
        assert cc.websocket is not None
        cc.websocket.send_text("not-json")
        with pytest.raises(WebSocketDisconnect) as malformed:
            cc.websocket.receive_json()
    assert malformed.value.code == 4400

    with FakeCC(client, computer_id, "correct-secret") as cc:
        assert cc.receive_json()["type"] == "hello_ack"
        assert cc.websocket is not None
        cc.websocket.send_text(" " * 5000)
        with pytest.raises(WebSocketDisconnect) as oversized:
            cc.websocket.receive_json()
    assert oversized.value.code == 4409


def test_missed_heartbeat_marks_device_offline(gateway_context) -> None:
    client, app, database_url, computer_id = gateway_context
    events = app.state.gateway.event_bus.subscribe()
    with FakeCC(client, computer_id, "correct-secret") as cc:
        assert cc.receive_json()["type"] == "hello_ack"
        assert events.get_nowait().name == "online"
        with pytest.raises(WebSocketDisconnect) as closed:
            cc.receive_json()
        assert closed.value.code == 4408
    assert read_computer_status(database_url, computer_id)[0] == ComputerStatus.OFFLINE
    assert events.get_nowait().name == "offline"
    app.state.gateway.event_bus.unsubscribe(events)


class FakeSocket:
    def __init__(self) -> None:
        self.sent: asyncio.Queue[str] = asyncio.Queue()
        self.close_code: int | None = None

    async def send_text(self, text: str) -> None:
        await self.sent.put(text)

    async def close(self, code: int, reason: str) -> None:
        self.close_code = code


@pytest.mark.asyncio
async def test_registry_call_correlates_reply_and_interrupt_is_out_of_band() -> None:
    settings = Settings(_env_file=None)
    gateway = WebSocketGateway(settings)
    socket = FakeSocket()
    connection = GatewayConnection("device-1", socket, settings)
    await gateway.registry.register("device-1", connection)

    pending = asyncio.create_task(
        gateway.registry.call(
            "device-1",
            ExecMessage(type="exec", id="exec-1", data={"code": "print('ok')"}),
            timeout=1,
        )
    )
    request = parse_message(await socket.sent.get())
    assert isinstance(request, ExecMessage)
    await gateway.registry.interrupt("device-1", InterruptMessage(type="interrupt", id="interrupt-1"))
    interrupt = parse_message(await socket.sent.get())
    assert isinstance(interrupt, InterruptMessage)

    await connection.receive(
        ExecResultMessage(
            type="exec_result",
            reply_to="exec-1",
            data={"ok": True, "output": "ok", "duration_ms": 1},
        ),
        gateway.event_bus,
        None,
    )
    response = await pending
    assert isinstance(response, ExecResultMessage)
    assert not connection.pending


@pytest.mark.asyncio
async def test_registry_call_timeout_cleans_pending_state() -> None:
    settings = Settings(_env_file=None)
    gateway = WebSocketGateway(settings)
    connection = GatewayConnection("device-1", FakeSocket(), settings)
    await gateway.registry.register("device-1", connection)

    with pytest.raises(TimeoutError):
        await gateway.registry.call(
            "device-1",
            ExecMessage(type="exec", id="timeout-1", data={"code": "sleep(1)"}),
            timeout=0.01,
        )
    assert connection.pending == {}


def test_client_errors_are_persisted_and_forwarded(gateway_context) -> None:
    client, app, database_url, computer_id = gateway_context
    events = app.state.gateway.event_bus.subscribe()
    with FakeCC(client, computer_id, "correct-secret") as cc:
        assert cc.receive_json()["type"] == "hello_ack"
        assert events.get_nowait().name == "online"
        cc.send_json(
            {
                "v": 1,
                "type": "error",
                "data": {"code": "client_failure", "message": "script failed", "details": {"line": 4}},
            }
        )
        assert cc.websocket is not None
        cc.websocket.send_text("not-json")
        with pytest.raises(WebSocketDisconnect):
            cc.websocket.receive_json()
        event = events.get_nowait()
        assert event.name == "error"
        assert event.details["code"] == "client_failure"

    async def read_audit() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            audit = await session.scalar(select(AuditEvent).where(AuditEvent.action == "client_error"))
            assert audit is not None
            assert audit.details["message"] == "script failed"
        await engine.dispose()

    asyncio.run(read_audit())
    app.state.gateway.event_bus.unsubscribe(events)
