"""T19, T20 — security primitives: jti claim and blocklist."""
from __future__ import annotations

import pytest

from app.core.security import (
    blocklist_token,
    create_access_token,
    decode_access_token,
    hash_password,
    is_blocked,
    verify_password,
)


def test_password_hashing_uses_bcrypt() -> None:
    password_hash = hash_password("StrongPassword123")

    assert password_hash.startswith("$2")
    assert verify_password("StrongPassword123", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_round_trip() -> None:
    token = create_access_token("user-1", "user@example.com", "admin")
    payload = decode_access_token(token)

    assert payload["sub"] == "user-1"
    assert payload["email"] == "user@example.com"
    assert payload["role"] == "admin"


def test_T19_access_token_includes_jti_claim() -> None:
    """T19: Every access token must carry a non-empty 'jti' field."""
    token = create_access_token("user-1", "user@example.com", "viewer")
    payload = decode_access_token(token)

    assert "jti" in payload, "Token is missing jti claim"
    assert isinstance(payload["jti"], str) and len(payload["jti"]) > 0


@pytest.mark.asyncio
async def test_T20_blocklisted_jti_is_blocked() -> None:
    """T20: After calling blocklist_token(jti), is_blocked(jti) must return True."""
    token = create_access_token("user-2", "other@example.com", "viewer")
    payload = decode_access_token(token)
    jti = payload["jti"]

    assert not await is_blocked(jti), "Token should not be blocked before blocklisting"
    await blocklist_token(jti)
    assert await is_blocked(jti), "Token should be blocked after blocklist_token call"
