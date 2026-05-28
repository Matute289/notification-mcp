"""Auth: hashing, key generation, and resolve_user."""
from __future__ import annotations

import pytest

from mcp_server.auth import generate_api_key, hash_key, resolve_user, _KEY_PREFIX


# ---------------------------------------------------------------------------
# Unit: hashing
# ---------------------------------------------------------------------------

def test_hash_key_deterministic():
    h1 = hash_key("nm_live_abc123", secret_key="secret")
    h2 = hash_key("nm_live_abc123", secret_key="secret")
    assert h1 == h2


def test_hash_key_different_secrets():
    h1 = hash_key("nm_live_abc123", secret_key="secret1")
    h2 = hash_key("nm_live_abc123", secret_key="secret2")
    assert h1 != h2


def test_hash_key_different_keys():
    h1 = hash_key("nm_live_abc123", secret_key="secret")
    h2 = hash_key("nm_live_xyz999", secret_key="secret")
    assert h1 != h2


def test_generate_api_key_has_prefix():
    key = generate_api_key()
    assert key.startswith(_KEY_PREFIX)


def test_generate_api_key_unique():
    keys = {generate_api_key() for _ in range(100)}
    assert len(keys) == 100


# ---------------------------------------------------------------------------
# Integration: resolve_user with mocked DB
# ---------------------------------------------------------------------------

class _FakeSettings:
    secret_key = "testsecretkey1234567890123456789"


class _FakePool:
    def __init__(self, stored: dict[str, int]):
        self._stored = stored  # key_hash → user_id

    async def fetchrow(self, query: str, key_hash: str):
        uid = self._stored.get(key_hash)
        if uid is not None:
            return {"user_id": uid}
        return None


import mcp_server.db as _db_module


async def test_resolve_user_valid_key(monkeypatch):
    settings = _FakeSettings()
    key = generate_api_key()
    key_hash = hash_key(key, secret_key=settings.secret_key)

    async def fake_lookup(h: str):
        return 42 if h == key_hash else None

    # Patch on db module — auth.py accesses it via `_db.lookup_user_by_key_hash`
    monkeypatch.setattr(_db_module, "lookup_user_by_key_hash", fake_lookup)
    result = await resolve_user(key, settings)  # type: ignore[arg-type]
    assert result == 42


async def test_resolve_user_wrong_key(monkeypatch):
    settings = _FakeSettings()

    async def fake_lookup(h: str):
        return None

    monkeypatch.setattr(_db_module, "lookup_user_by_key_hash", fake_lookup)
    result = await resolve_user(generate_api_key(), settings)  # type: ignore[arg-type]
    assert result is None


async def test_resolve_user_bad_prefix(monkeypatch):
    settings = _FakeSettings()
    called = []

    async def fake_lookup(h: str):
        called.append(h)
        return 42

    monkeypatch.setattr(_db_module, "lookup_user_by_key_hash", fake_lookup)
    result = await resolve_user("invalid_key_without_prefix", settings)  # type: ignore[arg-type]
    assert result is None
    assert not called  # prefix check short-circuits before DB
