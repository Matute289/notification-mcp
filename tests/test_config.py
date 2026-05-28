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


def test_valid_config():
    with patch.dict(os.environ, _BASE_ENV, clear=True):
        s = Settings()
    assert s.service_api_url == "http://localhost:8080"
    assert s.mcp_host == "0.0.0.0"


def test_requires_service_api_url():
    env = {k: v for k, v in _BASE_ENV.items() if k != "SERVICE_API_URL"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_requires_database_url():
    env = {k: v for k, v in _BASE_ENV.items() if k != "DATABASE_URL"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_requires_secret_key():
    env = {k: v for k, v in _BASE_ENV.items() if k != "SECRET_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_invalid_database_url():
    env = {**_BASE_ENV, "DATABASE_URL": "mysql://bad"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_secret_key_too_short():
    env = {**_BASE_ENV, "SECRET_KEY": "short"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_strips_trailing_slash():
    env = {**_BASE_ENV, "SERVICE_API_URL": "http://example.com/"}
    with patch.dict(os.environ, env, clear=True):
        s = Settings()
    assert s.service_api_url == "http://example.com"


def test_repr_hides_secrets():
    with patch.dict(os.environ, _BASE_ENV, clear=True):
        s = Settings()
    r = repr(s)
    assert "mysecret" not in r
    assert "***" in r


def test_stdio_requires_user_id():
    env = {**_BASE_ENV, "MCP_TRANSPORT": "stdio"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_stdio_with_user_id_ok():
    env = {**_BASE_ENV, "MCP_TRANSPORT": "stdio", "MCP_STDIO_USER_ID": "42"}
    with patch.dict(os.environ, env, clear=True):
        s = Settings()
    assert s.mcp_stdio_user_id == 42
