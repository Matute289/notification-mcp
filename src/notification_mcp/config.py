from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # NotificationEngine connection
    notification_engine_base_url: str = "http://localhost:8080"
    notification_engine_app_key: str = Field(..., min_length=1)
    notification_engine_app_secret: str = Field(..., min_length=1)

    # HTTP client
    http_timeout_s: float = 10.0
    http_max_connections: int = 50
    http_max_keepalive_connections: int = 20
    http_verify_tls: bool = True

    # MCP transport
    mcp_transport: Literal["sse", "http"] = "sse"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765
    mcp_log_level: str = "INFO"

    # Template L1 cache (seconds; 0 = disabled)
    template_cache_ttl_s: int = 300

    @field_validator("notification_engine_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode="after")
    def warn_if_public_bind(self) -> "Settings":
        if self.mcp_host not in ("127.0.0.1", "::1", "localhost"):
            logging.getLogger(__name__).warning(
                "MCP_HOST=%s — server is reachable from the network. "
                "Set MCP_HOST=127.0.0.1 to restrict to loopback.",
                self.mcp_host,
            )
        return self

    def __repr__(self) -> str:
        # Never leak the secret in repr/logs
        return (
            f"Settings(base_url={self.notification_engine_base_url!r}, "
            f"app_key={self.notification_engine_app_key!r}, "
            f"app_secret=***)"
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
