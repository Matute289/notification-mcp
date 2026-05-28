"""API key hashing, generation, and resolution."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from .config import Settings
from . import db as _db

_KEY_PREFIX = "nm_live_"


def generate_api_key() -> str:
    """Generate a new random API key (~256-bit entropy)."""
    return _KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str, *, secret_key: str) -> str:
    """Deterministic HMAC-SHA256(secret_key, key).

    Using HMAC instead of plain SHA-256 means the hash stored in DB is
    useless to an attacker who only has the DB — they also need SECRET_KEY.
    Deterministic (same key always → same hash) so we can look it up by index.
    """
    return hmac.new(secret_key.encode(), key.encode(), hashlib.sha256).hexdigest()


async def resolve_user(api_key: str, settings: Settings) -> int | None:
    """Return the user_id for a valid, non-revoked API key, or None."""
    if not api_key.startswith(_KEY_PREFIX):
        return None
    key_hash = hash_key(api_key, secret_key=settings.secret_key)
    return await _db.lookup_user_by_key_hash(key_hash)
