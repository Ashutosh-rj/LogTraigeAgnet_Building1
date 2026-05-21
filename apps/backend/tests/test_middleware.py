"""T16–T18 — rate limiting: auth bucket, global bucket, JSON 429 body."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.rate_limit import rate_limiter
from tests.conftest import auth_headers, register


def _reset_limiter() -> None:
    """Clear in-process rate limiter buckets between tests."""
    rate_limiter._local.clear()  # noqa: SLF001


@pytest.mark.asyncio
async def test_T16_auth_rate_limit_11th_login_returns_429(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T16: The 11th login attempt from the same IP within one window must return HTTP 429."""
    # Patch limit to 3 to keep the test fast; the middleware reads from settings at dispatch time.
    monkeypatch.setenv("AUTH_RATE_LIMIT_REQUESTS", "3")
    from app.core.config import get_settings
    get_settings.cache_clear()
    _reset_limiter()

    await register(client, email="victim@example.com")

    # Exhaust the auth bucket
    for _ in range(3):
        await client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": "Passw0rd!secure"},
        )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "victim@example.com", "password": "Passw0rd!secure"},
    )
    assert resp.status_code == 429, (
        f"Expected 429 after exceeding auth rate limit, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_T17_global_rate_limit_121st_request_returns_429(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T17: The request exceeding the global per-IP rate limit must return HTTP 429."""
    # Patch the global limit to 5 so we don't need 121 real requests.
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "5")
    from app.core.config import get_settings
    get_settings.cache_clear()
    _reset_limiter()

    data = await register(client, email="admin@example.com")
    token = data["access_token"]

    # Exhaust the global bucket using a real API endpoint (health is excluded from rate limiting).
    # Use /api/v1/incidents which requires auth and hits the global bucket.
    for _ in range(5):
        await client.get("/api/v1/incidents", headers=auth_headers(token))

    # The 6th request to the same endpoint must be rate-limited.
    resp = await client.get("/api/v1/incidents", headers=auth_headers(token))
    assert resp.status_code == 429, (
        f"Expected 429 after exceeding global rate limit, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_T18_429_response_body_is_json_with_detail_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T18: Every 429 response must carry a JSON body with a 'detail' key."""
    monkeypatch.setenv("AUTH_RATE_LIMIT_REQUESTS", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()
    _reset_limiter()

    await register(client, email="user@example.com")

    # Exhaust auth bucket
    await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Passw0rd!secure"},
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Passw0rd!secure"},
    )
    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"

    body = resp.json()
    assert "detail" in body, f"429 body must have 'detail' key, got: {body}"
    assert isinstance(body["detail"], str) and body["detail"], (
        f"'detail' must be a non-empty string, got: {body['detail']!r}"
    )
