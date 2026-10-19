from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aicontrol.api.computer_schemas import ExecRequest, InterruptRequest, RenameComputerRequest
from aicontrol.audit import record_request
from aicontrol.auth.sessions import SessionPrincipal, require_api_access
from aicontrol.db.models import Computer, ComputerStatus, ExecRun, User, new_id, utc_now
from aicontrol.db.session import get_session
from aicontrol.gateway.registry import GatewayEvent, WebSocketGateway
from aicontrol.permissions import PermissionRole, accessible_computers, require_computer_role
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
        "owner_team_id": computer.owner_team_id,
        "ownership": "team" if computer.owner_team_id else "personal",
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
    required: PermissionRole = PermissionRole.OWNER,
) -> Computer:
    computer, _ = await require_computer_role(user, computer_id, session, required)
    return computer


async def current_gateway(request: Request) -> WebSocketGateway:
    return request.app.state.gateway


@router.get("")
async def list_computers(
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:read"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    accessible = await accessible_computers(principal.user, session)
    result = [computer for computer, _ in accessible]
    result.sort(key=lambda computer: (str(computer.kind), computer.label))
    if principal.is_api_token and (
        principal.session.computer_ids is not None or principal.session.group_ids is not None
    ):
        allowed_ids = set(principal.session.computer_ids or [])
        if principal.session.group_ids:
            from aicontrol.db.models import GroupMember

            group_computer_ids = await session.scalars(
                select(GroupMember.computer_id).where(
                    GroupMember.group_id.in_(principal.session.group_ids)
                )
            )
            allowed_ids.update(group_computer_ids)
        user_allowed_ids = set()
        for computer_id in allowed_ids:
            try:
                await require_computer_role(
                    principal.user, computer_id, session, PermissionRole.VIEWER
                )
            except HTTPException:
                continue
            user_allowed_ids.add(computer_id)
        result = [computer for computer in result if computer.id in user_allowed_ids]
    roles_by_id = {computer.id: role.name.lower() for computer, role in accessible}
    return [{**_computer_payload(computer), "effective_role": roles_by_id[computer.id]} for computer in result]


@router.get("/{computer_id}")
async def get_computer(
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:read"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    computer, role = await require_computer_role(
        principal.user, computer_id, session, PermissionRole.VIEWER
    )
    return {**_computer_payload(computer), "effective_role": role.name.lower()}


@router.patch("/{computer_id}")
async def rename_computer(
    computer_id: str,
    payload: RenameComputerRequest,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:exec"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    computer = await _owned_computer(computer_id, principal.user, session)
    computer.label = payload.label
    await session.commit()
    await record_request(
        request, session, action="computer.rename", target_type="computer",
        target_id=computer.id, computer_id=computer.id, details={"label": payload.label},
        commit=False,
    )
    await session.commit()
    return _computer_payload(computer)


@router.get("/{computer_id}/runs")
async def list_runs(
    computer_id: str,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:read"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    await _owned_computer(computer_id, principal.user, session, PermissionRole.VIEWER)
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
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:exec"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
) -> dict[str, Any]:
    user = principal.user
    computer = await _owned_computer(computer_id, user, session, PermissionRole.OPERATOR)
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
    exec_message = ExecMessage(
        type="exec",
        id=run.id,
        data={"name": payload.name, "code": payload.code, "timeout_ms": payload.timeout_ms},
    )
    try:
        reply = await gateway.registry.call(
            computer_id,
            exec_message,
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
    await record_request(
        request,
        session,
        action="computer.exec",
        target_type="run",
        target_id=run.id,
        computer_id=computer.id,
        outcome="success" if result.get("ok") else "failure",
        details={"name": payload.name, "code": payload.code, "result": result},
        commit=False,
    )
    await session.commit()
    await gateway.event_bus.publish(
        GatewayEvent("exec_result", computer_id, details={"run_id": run.id, "result": result})
    )
    return {"run": _run_payload(run), "result": result}


@router.post("/{computer_id}/interrupt", status_code=status.HTTP_202_ACCEPTED)
async def interrupt_program(
    computer_id: str,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:exec"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
    payload: InterruptRequest | None = None,
) -> dict[str, str]:
    await _owned_computer(computer_id, principal.user, session, PermissionRole.OPERATOR)
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
    await record_request(
        request, session, action="computer.interrupt", target_type="computer",
        target_id=computer_id, computer_id=computer_id,
        details={"emergency": bool(payload and payload.emergency)},
    )
    return {"status": "interrupt_sent"}


@router.post("/{computer_id}/emergency-stop", status_code=status.HTTP_202_ACCEPTED)
async def emergency_stop(
    computer_id: str,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:exec"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[WebSocketGateway, Depends(current_gateway)],
) -> dict[str, str]:
    await _owned_computer(computer_id, principal.user, session, PermissionRole.OPERATOR)
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
    await record_request(
        request, session, action="computer.emergency_stop", target_type="computer",
        target_id=computer_id, computer_id=computer_id,
    )
    return {"status": "emergency_stop_sent"}


@router.post("/{computer_id}/reboot", status_code=status.HTTP_202_ACCEPTED)
async def reboot_computer(
    computer_id: str,
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_api_access("computers:exec"))],
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
    await record_request(
        request, session, action="computer.reboot", target_type="computer",
        target_id=computer_id, computer_id=computer_id,
    )
    return {"status": "reboot_requested"}
