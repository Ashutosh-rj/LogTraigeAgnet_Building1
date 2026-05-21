"""T01–T06 — authentication: bootstrap, rotation, blocklist."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefreshToken
from tests.conftest import auth_headers, login, register


@pytest.mark.asyncio
async def test_T01_first_registered_user_is_admin(client: AsyncClient) -> None:
    """T01: The first user to register on a fresh DB must receive the admin role."""
    data = await register(client, email="admin@example.com")

    assert data["user"]["role"] == "admin", (
        f"Expected first user to be admin, got {data['user']['role']!r}"
    )


@pytest.mark.asyncio
async def test_T02_second_registered_user_is_viewer(client: AsyncClient) -> None:
    """T02: Every subsequent registration must receive the viewer role."""
    await register(client, email="first@example.com", name="First")
    data = await register(client, email="second@example.com", name="Second")

    assert data["user"]["role"] == "viewer", (
        f"Expected second user to be viewer, got {data['user']['role']!r}"
    )


@pytest.mark.asyncio
async def test_T03_login_wrong_password_returns_401(client: AsyncClient) -> None:
    """T03: A login attempt with the wrong password must return HTTP 401."""
    await register(client, email="user@example.com")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "WrongPassw0rd!"},
    )

    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_T04_refresh_token_rotation_replaced_by_id_matches(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T04: After a token refresh, replaced_by_token_id must point to the new token's id."""
    await register(client, email="user@example.com")
    await login(client, email="user@example.com")
    # The refresh token is stored as an httpOnly cookie; httpx propagates it automatically.
    # Trigger refresh using the cookie (no body needed — the route reads cookies first).
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200, resp.text

    # After refresh, the old token in DB must have replaced_by_token_id set.
    # We identify it via the most-recently revoked token row.
    from sqlalchemy import select
    from app.db.models import RefreshToken as RT
    result = await db_session.execute(
        select(RT).where(RT.revoked_at.isnot(None)).order_by(RT.created_at.asc())
    )
    old_token_row = result.scalars().first()
    assert old_token_row is not None, "No revoked refresh token found after rotation"
    assert old_token_row.replaced_by_token_id is not None, "replaced_by_token_id must be set after rotation"

    # Confirm the replacement points to a real token row
    result2 = await db_session.execute(select(RT).where(RT.id == old_token_row.replaced_by_token_id))
    new_token_row = result2.scalar_one_or_none()
    assert new_token_row is not None, (
        f"replaced_by_token_id {old_token_row.replaced_by_token_id!r} does not match any token row"
    )
    old_hash = None  # unused below



@pytest.mark.asyncio
async def test_T05_logout_blocklists_access_token(client: AsyncClient) -> None:
    """T05: After logout the access token's jti must be in the blocklist."""
    await register(client, email="user@example.com")
    tokens = await login(client, email="user@example.com")
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    from app.core.security import decode_access_token, is_blocked
    payload = decode_access_token(access)
    jti = payload["jti"]

    assert not await is_blocked(jti), "jti should not be blocked before logout"

    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers=auth_headers(access),
    )
    assert resp.status_code == 200, resp.text

    assert await is_blocked(jti), "jti must be blocked after logout"


@pytest.mark.asyncio
async def test_T06_blocked_jti_on_protected_route_returns_401(client: AsyncClient) -> None:
    """T06: Using an access token whose jti has been blocklisted must return HTTP 401."""
    await register(client, email="user@example.com")
    tokens = await login(client, email="user@example.com")
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Logout to blocklist the jti
    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers=auth_headers(access),
    )

    # Protected route must now reject the revoked token
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(access))
    assert resp.status_code == 401, (
        f"Expected 401 after logout blocklist, got {resp.status_code}: {resp.text}"
    )
