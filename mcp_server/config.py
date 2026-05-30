from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- required (no defaults — fail fast if missing) ----
    service_api_url: str = Field(..., min_length=1)
    service_api_key: str = Field(..., min_length=1)
    service_api_secret: str = Field(..., min_length=1)
    database_url: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)

    # ---- optional with secure defaults ----
    mcp_transport: Literal["streamable_http", "stdio"] = "streamable_http"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_stdio_user_id: int | None = None
    rate_limit_per_minute: int = 60
    http_timeout_s: float = 10.0
    http_max_connections: int = 50
    http_max_keepalive_connections: int = 20
    http_verify_tls: bool = True
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    template_cache_ttl_s: int = 300

    @field_validator("service_api_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must start with postgresql:// or postgres://")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v.encode()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 bytes")
        return v

    @model_validator(mode="after")
    def validate_stdio_user_id(self) -> "Settings":
        if self.mcp_transport == "stdio" and self.mcp_stdio_user_id is None:
            raise ValueError(
                "MCP_STDIO_USER_ID is required when MCP_TRANSPORT=stdio "
                "and tools are user-scoped"
            )
        return self

    def __repr__(self) -> str:
        return (
            f"Settings(service_api_url={self.service_api_url!r}, "
            f"service_api_key={self.service_api_key[:8]}..., "
            f"service_api_secret=***, secret_key=***)"
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
