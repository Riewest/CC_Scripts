from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.api.computer_schemas import ExecRequest, InterruptRequest, RenameComputerRequest
from aicontrol.auth.sessions import SessionPrincipal, current_user, require_csrf
from aicontrol.db.models import Computer, ComputerStatus, ExecRun, User, new_id, utc_now
from aicontrol.db.session import get_session
from aicontrol.gateway.registry import GatewayEvent, WebSocketGateway
from aicontrol.protocol.models import ExecMessage, ExecResultMessage, InterruptMessage

router = APIRouter(prefix="/api/computers", tags=["computers"])


def _gateway(session: AsyncSession) -> WebSocketGateway:
    return session.info["gateway"]


def _computer_payload(computer: Computer) -> dict[str, Any]:
    return {
        "id": computer.id,
        "label": computer.label,
        "kind": str(computer.kind),
        "status": str(computer.status),
        "cc_version": computer.cc_version,
        "last_seen": computer.last_seen.isoformat() if computer.last_seen else None,
        "telemetry": computer.telemetry,
    }


def _run_payload(run: ExecRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "computer_id": run.computer_id,
        "actor_user_id": run.actor_user_id,
        "code": run.code,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "result": run.result,
    }


async def _owned_computer(
    computer_id: str,
    user: User,
    session: AsyncSession,
) -> Computer:
    computer = await session.get(Computer, computer_id)
    if computer is None or computer.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Computer not found")
    return computer


async def current_gateway(request: Request) -> WebSocketGateway:
    return request.app.state.gateway


@router.get("")
async def list_computers(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    computers = await session.scalars(
        select(Computer)
        .where(Computer.owner_user_id == user.id)
        .order_by(Computer.kind, Computer.label)
    )
    return [_computer_payload(computer) for computer in computers]


@router.get("/{computer_id}")
async def get_computer(
    computer_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    computer = await _owned_computer(computer_id, user, session)
    return _computer_payload(computer)


@router.patch("/{computer_id}")
async def rename_computer(
    computer_id: str,
    payload: RenameComputerRequest,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    computer = await _owned_computer(computer_id, principal.user, session)
    computer.label = payload.label
    await session.commit()
    return _computer_payload(computer)


@router.get("/{computer_id}/runs")
async def list_runs(
    computer_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    await _owned_computer(computer_id, user, session)
    runs = await session.scalars(
        select(ExecRun)
        .where(ExecRun.computer_id == computer_id)
        .order_by(ExecRun.started_at.desc())
        .limit(100)
    )
    return [_run_payload(run) for run in runs]


@router.post("/{computer_id}/exec")
async def execute_code(
    computer_id: str,
    payload: ExecRequest,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
) -> dict[str, Any]:
    user = principal.user
    computer = await _owned_computer(computer_id, user, session)
    if computer.status != ComputerStatus.ONLINE:
        raise HTTPException(status_code=409, detail="Computer is offline")
    run = ExecRun(
        id=new_id(),
        computer_id=computer.id,
        actor_user_id=user.id,
        code=payload.code,
        started_at=utc_now(),
    )
    session.add(run)
    await session.commit()
    request = ExecMessage(
        type="exec",
        id=run.id,
        data={"name": payload.name, "code": payload.code, "timeout_ms": payload.timeout_ms},
    )
    try:
        reply = await gateway.registry.call(
            computer_id,
            request,
            timeout=payload.timeout_ms / 1000 + 10,
        )
    except TimeoutError:
        result = {
            "ok": False,
            "output": "",
            "error": "Execution timed out waiting for the client",
            "traceback": None,
            "return_values": [],
            "duration_ms": (utc_now() - run.started_at).total_seconds() * 1000,
        }
    except (ConnectionError, OSError):
        result = {
            "ok": False,
            "output": "",
            "error": "Computer connection was lost during execution",
            "traceback": None,
            "return_values": [],
            "duration_ms": (utc_now() - run.started_at).total_seconds() * 1000,
        }
    else:
        if not isinstance(reply, ExecResultMessage):
            raise HTTPException(status_code=502, detail="Client returned an unexpected response")
        result = reply.data.model_dump(mode="json")
    run.finished_at = utc_now()
    run.result = result
    await session.commit()
    await gateway.event_bus.publish(
        GatewayEvent("exec_result", computer_id, details={"run_id": run.id, "result": result})
    )
    return {"run": _run_payload(run), "result": result}


@router.post("/{computer_id}/interrupt", status_code=status.HTTP_202_ACCEPTED)
async def interrupt_program(
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
    payload: InterruptRequest | None = None,
) -> dict[str, str]:
    await _owned_computer(computer_id, principal.user, session)
    try:
        await gateway.registry.interrupt(
            computer_id,
            InterruptMessage(
                type="interrupt",
                id=new_id(),
                data={"reason": "emergency" if payload and payload.emergency else "stop"},
            ),
        )
    except ConnectionError as exc:
        raise HTTPException(status_code=409, detail="Computer is offline") from exc
    return {"status": "interrupt_sent"}


@router.post("/{computer_id}/emergency-stop", status_code=status.HTTP_202_ACCEPTED)
async def emergency_stop(
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
) -> dict[str, str]:
    await _owned_computer(computer_id, principal.user, session)
    try:
        await gateway.registry.interrupt(
            computer_id,
            InterruptMessage(
                type="interrupt",
                id=new_id(),
                data={"reason": "emergency"},
            ),
        )
    except ConnectionError as exc:
        raise HTTPException(status_code=409, detail="Computer is offline") from exc
    return {"status": "emergency_stop_sent"}


@router.post("/{computer_id}/reboot", status_code=status.HTTP_202_ACCEPTED)
async def reboot_computer(
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
) -> dict[str, str]:
    computer = await _owned_computer(computer_id, principal.user, session)
    if computer.status != ComputerStatus.ONLINE:
        raise HTTPException(status_code=409, detail="Computer is offline")
    try:
        await gateway.registry.interrupt(
            computer_id,
            ExecMessage(
                type="exec",
                id=new_id(),
                data={"name": "web-reboot", "code": "os.reboot()", "timeout_ms": 1000},
            ),
        )
    except ConnectionError as exc:
        raise HTTPException(status_code=409, detail="Computer is offline") from exc
    return {"status": "reboot_requested"}
