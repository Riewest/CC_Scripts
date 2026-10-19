from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OidcProviderSettings(BaseModel):
    name: str
    issuer_url: str
    client_id: str
    client_secret: SecretStr = Field(repr=False)
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    allowed_email_domains: list[str] = Field(default_factory=list)
    auto_create_users: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
            raise ValueError("OIDC provider names may contain only letters, numbers, _ and -")
        return value

    @field_validator("issuer_url")
    @classmethod
    def validate_issuer(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("OIDC issuer_url must be an HTTPS URL without query or fragment")
        return value.rstrip("/")

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        if not value:
            raise ValueError("OIDC client_id must not be empty")
        return value


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
    oidc_providers: list[OidcProviderSettings] = Field(default_factory=list, repr=False)

    @model_validator(mode="after")
    def unique_oidc_provider_names(self) -> Settings:
        names = [provider.name for provider in self.oidc_providers]
        if len(names) != len(set(names)):
            raise ValueError("OIDC provider names must be unique")
        return self

    @field_validator("web_dist_dir", "client_dist_dir", mode="before")
    @classmethod
    def empty_web_dist_dir_is_unset(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
