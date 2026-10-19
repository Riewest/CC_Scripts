from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ChunkInfo(ProtocolModel):
    index: int = Field(ge=0)
    total: int = Field(gt=0)

    @model_validator(mode="after")
    def index_is_within_total(self) -> ChunkInfo:
        if self.index >= self.total:
            raise ValueError("chunk index must be less than total")
        return self


class DataModel(ProtocolModel):
    pass


class HelloData(DataModel):
    device_id: str = Field(min_length=1, max_length=36)
    secret: str = Field(min_length=1, max_length=512)
    kind: Literal["computer", "turtle", "pocket"]
    label: str = Field(min_length=1, max_length=120)
    cc_version: str | None = Field(default=None, max_length=80)
    client_version: str = Field(min_length=1, max_length=80)
    capabilities: list[str] = Field(default_factory=list, max_length=128)


class HelloMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["hello"]
    id: str | None = None
    reply_to: str | None = None
    data: HelloData


class HeartbeatData(DataModel):
    timestamp: str | None = None
    sequence: int | None = Field(default=None, ge=0)


class HeartbeatMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["heartbeat"]
    id: str | None = None
    reply_to: str | None = None
    data: HeartbeatData = Field(default_factory=HeartbeatData)


class TelemetryData(DataModel):
    values: dict[str, Any]
    timestamp: str | None = None


class TelemetryMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["telemetry"]
    id: str | None = None
    reply_to: str | None = None
    data: TelemetryData


class ExecResultData(DataModel):
    ok: bool
    return_values: list[Any] = Field(default_factory=list)
    output: str = ""
    error: str | None = None
    traceback: str | None = None
    duration_ms: float = Field(ge=0)

    @field_validator("return_values", mode="before")
    @classmethod
    def normalize_empty_return_values(cls, value: Any) -> Any:
        # CC:Tweaked's JSON serializer encodes an empty Lua table as `{}`.
        # The client uses an empty table when a program returns no values or errors.
        return [] if value == {} else value


class ExecResultMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["exec_result"]
    id: str | None = None
    reply_to: str | None = None
    data: ExecResultData


class ExecStartedData(DataModel):
    name: str | None = None
    started_at: str | None = None


class ExecStartedMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["exec_started"]
    id: str | None = None
    reply_to: str | None = None
    data: ExecStartedData = Field(default_factory=ExecStartedData)


class EventData(DataModel):
    name: str = Field(min_length=1, max_length=128)
    args: list[Any] = Field(default_factory=list)


class EventMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["event"]
    id: str | None = None
    reply_to: str | None = None
    data: EventData


class TerminalFrameData(DataModel):
    width: int = Field(gt=0, le=512)
    height: int = Field(gt=0, le=512)
    lines: list[str]
    cursor_x: int | None = Field(default=None, ge=1)
    cursor_y: int | None = Field(default=None, ge=1)
    cursor_blink: bool = False


class TerminalFrameMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["term_frame"]
    id: str | None = None
    reply_to: str | None = None
    data: TerminalFrameData


class FsResultData(DataModel):
    operation_id: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=1, max_length=1024)
    ok: bool
    entries: list[dict[str, Any]] | None = None
    content: str | None = None
    error: str | None = None


class FsResultMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["fs_result"]
    id: str | None = None
    reply_to: str | None = None
    data: FsResultData


class PeripheralResultData(DataModel):
    name: str = Field(min_length=1, max_length=128)
    method: str = Field(min_length=1, max_length=128)
    ok: bool
    result: Any = None
    error: str | None = None


class PeripheralResultMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["peripheral_result"]
    id: str | None = None
    reply_to: str | None = None
    data: PeripheralResultData


class HelloAckData(DataModel):
    accept: bool
    device_secret: str | None = None
    session_id: str | None = None
    heartbeat_interval_s: int = Field(default=30, gt=0, le=3600)
    max_message_bytes: int = Field(default=131072, gt=0)
    reason: str | None = None


class HelloAckMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["hello_ack"]
    id: str | None = None
    reply_to: str | None = None
    data: HelloAckData


class ExecData(DataModel):
    code: str = Field(min_length=1)
    name: str = Field(default="remote", max_length=128)
    timeout_ms: int = Field(default=30000, gt=0)


class ExecMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["exec"]
    id: str = Field(min_length=1, max_length=128)
    reply_to: str | None = None
    data: ExecData


class InterruptData(DataModel):
    reason: str | None = None


class InterruptMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["interrupt"]
    id: str | None = None
    reply_to: str | None = None
    data: InterruptData = Field(default_factory=InterruptData)


class UpdateClientData(DataModel):
    version: str = Field(min_length=1, max_length=80)
    files: dict[str, str] | None = None
    url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def exactly_one_update_source(self) -> UpdateClientData:
        if (self.files is None) == (self.url is None):
            raise ValueError("exactly one of files or url must be provided")
        return self


class UpdateClientMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["update_client"]
    id: str | None = None
    reply_to: str | None = None
    data: UpdateClientData


class FsOperationData(DataModel):
    operation_id: str = Field(min_length=1, max_length=128)
    operation: Literal["read", "write", "list", "delete", "mkdir"]
    path: str = Field(min_length=1, max_length=1024)
    content: str | None = None


class FsOperationMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["fs_op"]
    id: str = Field(min_length=1, max_length=128)
    reply_to: str | None = None
    data: FsOperationData


class PeripheralCallData(DataModel):
    name: str = Field(min_length=1, max_length=128)
    method: str = Field(min_length=1, max_length=128)
    args: list[Any] = Field(default_factory=list)


class PeripheralCallMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["peripheral_call"]
    id: str = Field(min_length=1, max_length=128)
    reply_to: str | None = None
    data: PeripheralCallData


class TerminalInputData(DataModel):
    text: str = Field(max_length=4096)


class TerminalInputMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["term_input"]
    id: str | None = None
    reply_to: str | None = None
    data: TerminalInputData


class ConfigData(DataModel):
    settings: dict[str, Any]


class ConfigMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["config"]
    id: str | None = None
    reply_to: str | None = None
    data: ConfigData


class ErrorData(DataModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=1024)
    details: dict[str, Any] | None = None


class ErrorMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["error"]
    id: str | None = None
    reply_to: str | None = None
    data: ErrorData


class ChunkData(DataModel):
    message_type: str = Field(min_length=1, max_length=64)
    payload: str


class ChunkMessage(ProtocolModel):
    v: Literal[1] = 1
    type: Literal["chunk"]
    id: str = Field(min_length=1, max_length=128)
    reply_to: str | None = None
    chunk: ChunkInfo
    data: ChunkData


ProtocolMessage = Annotated[
    HelloMessage
    | HeartbeatMessage
    | TelemetryMessage
    | ExecResultMessage
    | ExecStartedMessage
    | EventMessage
    | TerminalFrameMessage
    | FsResultMessage
    | PeripheralResultMessage
    | HelloAckMessage
    | ExecMessage
    | InterruptMessage
    | UpdateClientMessage
    | FsOperationMessage
    | PeripheralCallMessage
    | TerminalInputMessage
    | ConfigMessage
    | ErrorMessage
    | ChunkMessage,
    Field(discriminator="type"),
]

protocol_adapter: TypeAdapter[ProtocolMessage] = TypeAdapter(ProtocolMessage)
