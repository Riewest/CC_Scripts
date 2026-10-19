from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100_000)
    name: str = Field(default="web", min_length=1, max_length=128)
    timeout_ms: int = Field(default=30_000, ge=100, le=300_000)


class RenameComputerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("label cannot be blank")
        return normalized


class InterruptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emergency: bool = False


class ComputerResponse(BaseModel):
    id: str
    label: str
    kind: str
    status: str
    cc_version: str | None
    last_seen: str | None
    telemetry: dict[str, Any] | None


class RunResponse(BaseModel):
    id: str
    computer_id: str
    actor_user_id: str | None
    code: str
    started_at: str
    finished_at: str | None
    result: dict[str, Any] | None


class ExecResponse(BaseModel):
    run: RunResponse
    result: dict[str, Any]
