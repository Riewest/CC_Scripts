import asyncio
import threading

from fakecc import FakeCC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aicontrol.db.models import Computer, ExecRun, User
from aicontrol.db.security import hash_secret


def authenticate(client) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": "gateway-owner", "password": "gateway-owner-password"},
    )
    assert response.status_code == 200
    return client.cookies["aic_csrf"]


def test_owned_computer_api_lists_detail_and_disallows_offline_execution(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    csrf = authenticate(client)
    computers = client.get("/api/computers")

    assert computers.status_code == 200
    assert [computer["id"] for computer in computers.json()] == [computer_id]
    assert client.get(f"/api/computers/{computer_id}").status_code == 200
    assert client.get("/api/computers/not-owned").status_code == 404
    assert client.post(
        f"/api/computers/{computer_id}/exec",
        headers={"x-csrf-token": csrf},
        json={"code": "print('offline')"},
    ).status_code == 409


def test_other_user_cannot_list_or_access_owned_computer(gateway_context) -> None:
    client, _, database_url, computer_id = gateway_context
    csrf = authenticate(client)

    async def add_second_user() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                User(
                    username="other-owner",
                    password_hash=hash_secret("other-long-password"),
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(add_second_user())
    client.post(
        "/api/auth/logout",
        headers={"x-csrf-token": csrf},
    )
    other_login = client.post(
        "/api/auth/login",
        json={"username": "other-owner", "password": "other-long-password"},
    )
    assert other_login.status_code == 200
    assert client.get("/api/computers").json() == []
    assert client.get(f"/api/computers/{computer_id}").status_code == 404


def test_exec_endpoint_runs_code_persists_result_and_returns_output(gateway_context) -> None:
    client, _, database_url, computer_id = gateway_context
    csrf = authenticate(client)
    results: list[dict] = []
    errors: list[BaseException] = []

    def send_exec() -> None:
        try:
            response = client.post(
                f"/api/computers/{computer_id}/exec",
                headers={"x-csrf-token": csrf},
                json={"code": "print('hello from turtle')\nreturn 42", "timeout_ms": 5000},
            )
            results.append({"status": response.status_code, "body": response.json()})
        except BaseException as exc:
            errors.append(exc)

    with FakeCC(client, computer_id, "correct-secret") as cc:
        cc.receive_json()
        caller = threading.Thread(target=send_exec)
        caller.start()
        request = cc.receive_json()
        assert request["type"] == "exec"
        cc.send_json(
            {
                "v": 1,
                "type": "exec_result",
                "reply_to": request["id"],
                "data": {
                    "ok": True,
                    "return_values": [42],
                    "output": "hello from turtle\n",
                    "duration_ms": 2,
                },
            }
        )
        caller.join(timeout=3)
        assert not caller.is_alive()
        assert not errors
        assert results[0]["status"] == 200
        assert results[0]["body"]["result"]["return_values"] == [42]
        assert results[0]["body"]["result"]["output"] == "hello from turtle\n"
        cc.disconnect()

    async def read_runs() -> tuple[int, dict]:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            runs = list(await session.scalars(select(ExecRun).where(ExecRun.computer_id == computer_id)))
            assert len(runs) == 1
            return len(runs), {"code": runs[0].code, "result": runs[0].result}

    count, stored = asyncio.run(read_runs())
    assert count == 1
    assert "return 42" in stored["code"]
    assert stored["result"]["ok"] is True
    assert client.get(f"/api/computers/{computer_id}/runs").json()[0]["result"]["ok"] is True


def test_exec_endpoint_returns_and_persists_runtime_traceback(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    csrf = authenticate(client)
    result_holder: list[dict] = []

    def post_run() -> None:
        response = client.post(
            f"/api/computers/{computer_id}/exec",
            headers={"x-csrf-token": csrf},
            json={"code": "error('test failure')", "timeout_ms": 5000},
        )
        result_holder.append(response.json())

    with FakeCC(client, computer_id, "correct-secret") as cc:
        cc.receive_json()
        caller = threading.Thread(target=post_run)
        caller.start()
        request = cc.receive_json()
        cc.send_json(
            {
                "v": 1,
                "type": "exec_result",
                "reply_to": request["id"],
                "data": {
                    "ok": False,
                    "error": "test failure",
                    "traceback": "remote.lua:1: test failure\\nstack traceback",
                    "output": "before error\\n",
                    "duration_ms": 3,
                },
            }
        )
        caller.join(timeout=3)
        assert not caller.is_alive()
        assert result_holder[0]["result"]["error"] == "test failure"
        assert "stack traceback" in result_holder[0]["result"]["traceback"]
        assert result_holder[0]["result"]["output"] == "before error\\n"
        cc.disconnect()


def test_interrupt_endpoint_sends_out_of_band_message(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    csrf = authenticate(client)
    errors: list[BaseException] = []
    statuses: list[int] = []

    def send_interrupt() -> None:
        try:
            response = client.post(
                f"/api/computers/{computer_id}/interrupt",
                headers={"x-csrf-token": csrf},
            )
            statuses.append(response.status_code)
        except BaseException as exc:
            errors.append(exc)

    with FakeCC(client, computer_id, "correct-secret") as cc:
        cc.receive_json()
        caller = threading.Thread(target=send_interrupt)
        caller.start()
        interrupt = cc.receive_json()
        assert interrupt["type"] == "interrupt"
        caller.join(timeout=2)
        assert not caller.is_alive()
        assert not errors
        assert statuses == [202]
        cc.disconnect()


def test_emergency_stop_interrupts_active_and_cancels_queued_exec(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    csrf = authenticate(client)
    run_responses: dict[str, dict] = {}
    interrupt_responses: list[int] = []
    failures: list[BaseException] = []

    def post_run(run_key: str, code: str) -> None:
        try:
            response = client.post(
                f"/api/computers/{computer_id}/exec",
                headers={"x-csrf-token": csrf},
                json={"code": code, "timeout_ms": 5000},
            )
            run_responses[run_key] = {"status": response.status_code, "body": response.json()}
        except BaseException as exc:
            failures.append(exc)

    def post_interrupt() -> None:
        try:
            response = client.post(
                f"/api/computers/{computer_id}/emergency-stop",
                headers={"x-csrf-token": csrf},
            )
            interrupt_responses.append(response.status_code)
        except BaseException as exc:
            failures.append(exc)

    with FakeCC(client, computer_id, "correct-secret") as cc:
        cc.receive_json()
        run_thread = threading.Thread(target=post_run, args=("active", "while true do end"))
        run_thread.start()
        active_request = cc.receive_json()
        assert active_request["type"] == "exec"
        queued_thread = threading.Thread(target=post_run, args=("queued", "print('queued')"))
        queued_thread.start()
        queued_request = cc.receive_json()
        assert queued_request["type"] == "exec"
        interrupt_thread = threading.Thread(target=post_interrupt)
        interrupt_thread.start()
        interrupt_message = cc.receive_json()
        assert interrupt_message["type"] == "interrupt"
        assert interrupt_message["data"]["reason"] == "emergency"
        interrupt_thread.join(timeout=2)
        assert not interrupt_thread.is_alive()
        assert interrupt_responses == [202]
        cc.send_json(
            {
                "v": 1,
                "type": "exec_result",
                "reply_to": queued_request["id"],
                "data": {
                    "ok": False,
                    "error": "Cancelled by emergency stop",
                    "traceback": "Execution was cancelled before it started.",
                    "duration_ms": 0,
                },
            }
        )
        queued_thread.join(timeout=2)
        assert not queued_thread.is_alive()
        assert run_responses["queued"]["status"] == 200
        assert run_responses["queued"]["body"]["result"]["error"] == "Cancelled by emergency stop"
        cc.send_json(
            {
                "v": 1,
                "type": "exec_result",
                "reply_to": active_request["id"],
                "data": {"ok": False, "error": "Interrupted", "traceback": "interrupted", "duration_ms": 5},
            }
        )
        run_thread.join(timeout=3)
        assert not run_thread.is_alive()
        assert not failures
        assert run_responses["active"]["status"] == 200
        assert run_responses["active"]["body"]["result"]["error"] == "Interrupted"
        cc.disconnect()


def test_protected_mutation_requires_csrf(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    authenticate(client)
    response = client.post(
        f"/api/computers/{computer_id}/interrupt",
    )
    assert response.status_code == 403


def test_rename_computer_is_owner_and_csrf_protected(gateway_context) -> None:
    client, _, _, computer_id = gateway_context
    csrf = authenticate(client)
    denied = client.patch(
        f"/api/computers/{computer_id}",
        json={"label": "Renamed turtle"},
    )
    assert denied.status_code == 403
    renamed = client.patch(
        f"/api/computers/{computer_id}",
        headers={"x-csrf-token": csrf},
        json={"label": " Renamed turtle "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["label"] == "Renamed turtle"


def test_telemetry_is_persisted_when_received_from_computer(gateway_context) -> None:
    client, _, database_url, computer_id = gateway_context

    async def read_telemetry() -> dict:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            computer = await session.get(Computer, computer_id)
            assert computer is not None
            telemetry = computer.telemetry
        await engine.dispose()
        return telemetry

    async def wait_for_telemetry() -> dict | None:
        for _ in range(100):
            telemetry = await read_telemetry()
            if telemetry is not None:
                return telemetry
            await asyncio.sleep(0.01)
        return None

    with FakeCC(client, computer_id, "correct-secret") as cc:
        assert cc.receive_json()["type"] == "hello_ack"
        cc.send_json(
            {
                "v": 1,
                "type": "telemetry",
                "data": {"values": {"fuel": 321, "kind": "computer"}},
            }
        )
        telemetry = asyncio.run(wait_for_telemetry())
        assert telemetry is not None and telemetry["fuel"] == 321
        cc.disconnect()
