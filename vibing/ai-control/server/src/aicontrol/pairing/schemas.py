from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreatePairingCode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = "me"
    label: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, owner: str) -> str:
        normalized = owner.strip()
        if not normalized or len(normalized) > 80:
            raise ValueError("owner must be 'me' or a team identifier")
        return normalized

    @field_validator("label")
    @classmethod
    def normalize_label(cls, label: str | None) -> str | None:
        if label is None:
            return None
        normalized = label.strip()
        if not normalized:
            raise ValueError("label cannot be blank")
        return normalized


class PairingCodeResponse(BaseModel):
    id: str
    code: str
    expires_at: str
    command: str


class PairingStatusResponse(BaseModel):
    id: str
    expires_at: str
    used: bool
    paired_computer: dict[str, str | None] | None = None
