from pydantic import BaseModel, ConfigDict, Field, field_validator


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized or any(character.isspace() for character in normalized):
            raise ValueError("username must be non-empty and contain no whitespace")
        return normalized


class UserResponse(BaseModel):
    id: str
    username: str
    role: str


class SetupState(BaseModel):
    setup_required: bool
    signup_allowed: bool


class ChangePassword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)
