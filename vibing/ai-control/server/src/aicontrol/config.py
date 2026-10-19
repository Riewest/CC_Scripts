from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIC_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    max_ws_message_bytes: int = Field(default=131072, gt=0)
    hello_timeout_s: float = Field(default=5.0, gt=0)
    heartbeat_interval_s: int = Field(default=30, gt=0)
    heartbeat_timeout_s: float = Field(default=90.0, gt=0)
    database_url: str = "sqlite:///./aicontrol.db"
    environment: str = "development"
    allow_signup: bool = False
    public_url: str = "http://localhost:8000"
    web_dist_dir: Path | None = None
    client_dist_dir: Path | None = None
    secret_encryption_key: str | None = None

    @field_validator("web_dist_dir", "client_dist_dir", mode="before")
    @classmethod
    def empty_web_dist_dir_is_unset(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
