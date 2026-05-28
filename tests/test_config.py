"""Config validation tests."""
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import mcp_server.config as _config_module
from mcp_server.config import Settings

_BASE_ENV = {
    "SERVICE_API_URL": "http://localhost:8080",
    "SERVICE_API_KEY": "mykey",
    "SERVICE_API_SECRET": "mysecret",
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/test",
    "SECRET_KEY": "a" * 32,
    "MCP_TRANSPORT": "streamable_http",
}


@pytest.fixture(autouse=True)
def reset_settings():
    _config_module._settings = None
    yield
    _config_module._settings = None


def _s(**overrides):
    """Instantiate Settings from _BASE_ENV, ignoring any .env file."""
    env = {**_BASE_ENV, **overrides}
    with patch.dict(os.environ, env, clear=True):
        return Settings(_env_file=None)  # type: ignore[call-arg]


def _s_missing(key: str):
    env = {k: v for k, v in _BASE_ENV.items() if k != key}
    with patch.dict(os.environ, env, clear=True):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_valid_config():
    s = _s()
    assert s.service_api_url == "http://localhost:8080"
    assert s.mcp_host == "0.0.0.0"


def test_requires_service_api_url():
    with pytest.raises((ValidationError, Exception)):
        _s_missing("SERVICE_API_URL")


def test_requires_database_url():
    with pytest.raises((ValidationError, Exception)):
        _s_missing("DATABASE_URL")


def test_requires_secret_key():
    with pytest.raises((ValidationError, Exception)):
        _s_missing("SECRET_KEY")


def test_invalid_database_url():
    with pytest.raises((ValidationError, Exception)):
        _s(DATABASE_URL="mysql://bad")


def test_secret_key_too_short():
    with pytest.raises((ValidationError, Exception)):
        _s(SECRET_KEY="short")


def test_strips_trailing_slash():
    s = _s(SERVICE_API_URL="http://example.com/")
    assert s.service_api_url == "http://example.com"


def test_repr_hides_secrets():
    s = _s()
    r = repr(s)
    assert "mysecret" not in r
    assert "***" in r


def test_stdio_requires_user_id():
    with pytest.raises((ValidationError, Exception)):
        _s(MCP_TRANSPORT="stdio")


def test_stdio_with_user_id_ok():
    s = _s(MCP_TRANSPORT="stdio", MCP_STDIO_USER_ID="42")
    assert s.mcp_stdio_user_id == 42
