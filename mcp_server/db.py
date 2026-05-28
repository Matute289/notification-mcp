"""asyncpg connection pool + schema bootstrap."""
from __future__ import annotations

import asyncpg

from .config import Settings

_pool: asyncpg.Pool | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
"""


async def connect(settings: Settings) -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        await conn.execute(_SCHEMA)


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call db.connect() first.")
    return _pool


async def lookup_user_by_key_hash(key_hash: str) -> int | None:
    row = await get_pool().fetchrow(
        "SELECT user_id FROM api_keys WHERE key_hash = $1 AND revoked_at IS NULL",
        key_hash,
    )
    return row["user_id"] if row else None
