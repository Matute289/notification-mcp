"""CLI for managing API keys.

Usage:
    python -m mcp_server.scripts.keys create --user-id 42 --name "Claude Desktop"
    python -m mcp_server.scripts.keys list --user-id 42
    python -m mcp_server.scripts.keys revoke <key-id>
"""
from __future__ import annotations

import asyncio
from typing import Annotated

import asyncpg
import cyclopts
from cyclopts import App, Parameter

from ..auth import generate_api_key, hash_key
from ..config import get_settings

app = App(name="keys", help="Manage MCP server API keys.")


@app.command
async def create(
    user_id: Annotated[int, Parameter(help="User ID this key belongs to.")],
    name: Annotated[str, Parameter(help="Human-readable label.")] = "",
) -> None:
    """Generate a new API key and store its hash in the database."""
    settings = get_settings()
    key = generate_api_key()
    key_hash = hash_key(key, secret_key=settings.secret_key)

    conn = await asyncpg.connect(settings.database_url)
    try:
        row = await conn.fetchrow(
            "INSERT INTO api_keys (user_id, key_hash, name) VALUES ($1, $2, $3) RETURNING id",
            user_id, key_hash, name or None,
        )
    finally:
        await conn.close()

    print(f"\nAPI Key created (shown once — store it securely):\n\n  {key}\n")
    print(f"Key ID: {row['id']}  |  User: {user_id}  |  Name: {name or '(none)'}")


@app.command
async def list(
    user_id: Annotated[int | None, Parameter(help="Filter by user ID.")] = None,
) -> None:
    """List API keys (never shows the cleartext key)."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        if user_id is not None:
            rows = await conn.fetch(
                "SELECT id, user_id, name, key_hash, created_at, revoked_at "
                "FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC",
                user_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, user_id, name, key_hash, created_at, revoked_at "
                "FROM api_keys ORDER BY created_at DESC"
            )
    finally:
        await conn.close()

    if not rows:
        print("No API keys found.")
        return

    print(f"{'ID':<6} {'UserID':<10} {'Name':<20} {'Prefix':<12} {'Created':<22} {'Revoked'}")
    print("-" * 85)
    for r in rows:
        revoked = str(r["revoked_at"])[:19] if r["revoked_at"] else "—"
        print(
            f"{r['id']:<6} {r['user_id']:<10} {(r['name'] or ''):<20} "
            f"{r['key_hash'][:12]:<12} {str(r['created_at'])[:19]:<22} {revoked}"
        )


@app.command
async def revoke(
    key_id: Annotated[int, Parameter(help="Key ID to revoke (from `list`).")],
) -> None:
    """Revoke an API key by its ID."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        result = await conn.execute(
            "UPDATE api_keys SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL",
            key_id,
        )
    finally:
        await conn.close()

    if result == "UPDATE 1":
        print(f"Key {key_id} revoked.")
    else:
        print(f"Key {key_id} not found or already revoked.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
