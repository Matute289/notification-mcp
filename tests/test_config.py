"""Config validation tests."""
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from notification_mcp.config import Settings


def test_requires_app_key():
    env = {
        "NOTIFICATION_ENGINE_APP_SECRET": "secret",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_requires_app_secret():
    env = {
        "NOTIFICATION_ENGINE_APP_KEY": "key",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((ValidationError, Exception)):
            Settings()


def test_valid_minimal_config():
    env = {
        "NOTIFICATION_ENGINE_APP_KEY": "mykey",
        "NOTIFICATION_ENGINE_APP_SECRET": "mysecret",
    }
    with patch.dict(os.environ, env, clear=True):
        s = Settings()
    assert s.notification_engine_base_url == "http://localhost:8080"
    assert s.mcp_host == "127.0.0.1"
    assert s.mcp_port == 8765


def test_strips_trailing_slash():
    env = {
        "NOTIFICATION_ENGINE_APP_KEY": "k",
        "NOTIFICATION_ENGINE_APP_SECRET": "s",
        "NOTIFICATION_ENGINE_BASE_URL": "http://example.com/",
    }
    with patch.dict(os.environ, env, clear=True):
        s = Settings()
    assert s.notification_engine_base_url == "http://example.com"


def test_repr_hides_secret():
    env = {
        "NOTIFICATION_ENGINE_APP_KEY": "mykey",
        "NOTIFICATION_ENGINE_APP_SECRET": "supersecret",
    }
    with patch.dict(os.environ, env, clear=True):
        s = Settings()
    assert "supersecret" not in repr(s)
    assert "***" in repr(s)
