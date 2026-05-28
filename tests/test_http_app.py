"""HTTP layer tests: /health, auth, 401, rate-limit."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from httpx import ASGITransport

import mcp_server.config as _config_module
import mcp_server.db as _db_module
import mcp_server.services.service_api_client as _client_module

_BASE_ENV = {
    "SERVICE_API_URL": "http://localhost:8080",
    "SERVICE_API_KEY": "testkey",
    "SERVICE_API_SECRET": "testsecret",
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/test",
    "SECRET_KEY": "a" * 32,
    "MCP_TRANSPORT": "streamable_http",
    "TEMPLATE_CACHE_TTL_S": "0",
}

_TEST_KEY = "nm_live_testkey0000000000000000000000000"
_TEST_USER_ID = 99


@pytest.fixture(autouse=True)
def reset_singletons():
    _config_module._settings = None
    _client_module._client = None
    _db_module._pool = None
    yield
    _config_module._settings = None
    _client_module._client = None
    _db_module._pool = None


@pytest.fixture
def patched_env():
    with patch.dict(os.environ, _BASE_ENV, clear=True):
        yield


@pytest.fixture
def mock_db(monkeypatch):
    """Stub out DB: our test key resolves to _TEST_USER_ID."""
    from mcp_server.auth import hash_key
    good_hash = hash_key(_TEST_KEY, secret_key="a" * 32)

    async def fake_lookup(h: str):
        return _TEST_USER_ID if h == good_hash else None

    monkeypatch.setattr(_db_module, "lookup_user_by_key_hash", fake_lookup)

    async def fake_connect(settings):
        pass

    async def fake_disconnect():
        pass

    monkeypatch.setattr(_db_module, "connect", fake_connect)
    monkeypatch.setattr(_db_module, "disconnect", fake_disconnect)


@pytest.fixture
def mock_service_client(monkeypatch):
    async def fake_init(settings):
        pass

    async def fake_close():
        pass

    monkeypatch.setattr(_client_module, "init", fake_init)
    monkeypatch.setattr(_client_module, "close", fake_close)


@pytest.fixture
async def test_client(patched_env, mock_db, mock_service_client):
    from mcp_server.app import create_app
    app = create_app()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# /health — no auth required
# ---------------------------------------------------------------------------

async def test_health_no_auth(test_client):
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 401 cases
# ---------------------------------------------------------------------------

async def test_missing_auth_header(test_client):
    resp = await test_client.post("/mcp")
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


async def test_invalid_bearer_token(test_client):
    resp = await test_client.post("/mcp", headers={"Authorization": "Bearer nm_live_wrongtoken"})
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


async def test_malformed_auth_header(test_client):
    resp = await test_client.post("/mcp", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Valid token reaches MCP (returns MCP-level response, not 401)
# ---------------------------------------------------------------------------

async def test_valid_token_passes_auth(test_client):
    # A valid MCP request with a valid token should NOT return 401.
    # (It may return an MCP error if the method is wrong, but auth passed.)
    resp = await test_client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {_TEST_KEY}",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert resp.status_code != 401
