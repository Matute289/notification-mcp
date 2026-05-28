"""Cross-language HMAC vector tests.

The expected hashes are pre-computed to match the Go implementation in
NotificationEngine/internal/platform/auth/hmac.go.

Canonical string (no trailing newline after body):
    timestamp \\n method \\n path \\n on_behalf_of \\n body

Computed via:
    echo -n "timestamp\\nmethod\\npath\\non_behalf_of\\nbody" | \
        openssl dgst -sha256 -hmac "secret"
"""
import hashlib
import hmac as _hmac
import time
from unittest.mock import patch

import pytest

from mcp_server.hmac_auth import _sign, build_auth_headers


# Fixed test vectors (recompute to verify cross-language parity)
#
# secret="testsecret", timestamp="1700000000", method="POST",
# path="/v1/notifications", on_behalf_of="", body=b""
_EXPECTED_NO_OBO = "cd02672ebab5104167163723510c90377277363ae5bcead01dc1951e40a85d61"

# same but on_behalf_of="42"
_EXPECTED_WITH_OBO = "9c76c0d63cf990b4042e8bd90bb3529a9a6b8feee4a7840ee70020bfc8257d6e"


def _compute(secret: str, timestamp: str, method: str, path: str, on_behalf_of: str, body: bytes) -> str:
    canonical = "\n".join([timestamp, method.upper(), path, on_behalf_of])
    msg = canonical.encode() + b"\n" + body
    return _hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def test_sign_no_on_behalf_of():
    result = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "", b"")
    assert result == _EXPECTED_NO_OBO


def test_sign_with_on_behalf_of():
    result = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "42", b"")
    assert result == _EXPECTED_WITH_OBO


def test_sign_differs_with_different_obo():
    r1 = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "42", b"")
    r2 = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "99", b"")
    assert r1 != r2


def test_sign_differs_without_obo_vs_with():
    r_empty = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "", b"")
    r_42 = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "42", b"")
    assert r_empty != r_42


def test_build_auth_headers_no_obo():
    with patch("mcp_server.hmac_auth.time") as mock_time:
        mock_time.time.return_value = 1700000000.0
        headers = build_auth_headers("mykey", "testsecret", "POST", "/v1/notifications", b"")

    assert headers["X-App-Key"] == "mykey"
    assert headers["X-App-Timestamp"] == "1700000000"
    assert "X-On-Behalf-Of-User" not in headers
    expected_sig = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "", b"")
    assert headers["X-App-Signature"] == expected_sig


def test_build_auth_headers_with_obo():
    with patch("mcp_server.hmac_auth.time") as mock_time:
        mock_time.time.return_value = 1700000000.0
        headers = build_auth_headers("mykey", "testsecret", "POST", "/v1/notifications", b"", on_behalf_of_user_id=42)

    assert headers["X-On-Behalf-Of-User"] == "42"
    expected_sig = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "42", b"")
    assert headers["X-App-Signature"] == expected_sig


def test_tampering_obo_invalidates_signature():
    """If on_behalf_of changes after signing, verification would fail (simulated)."""
    signed_sig = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "42", b"")
    # Simulate verifier seeing a tampered header value
    recomputed = _sign("testsecret", "1700000000", "POST", "/v1/notifications", "99", b"")
    assert not _hmac.compare_digest(signed_sig, recomputed)
