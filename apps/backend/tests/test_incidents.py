"""T07–T13 — incident lifecycle: notifications, soft delete, validation."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from tests.conftest import auth_headers, login, register


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

async def _admin_token(client: AsyncClient) -> str:
    data = await register(client, email="admin@example.com", name="Admin")
    return data["access_token"]


async def _create_assignee(client: AsyncClient, admin_token: str) -> dict:
    """Register a second (viewer) user to be used as an assignee."""
    # Register as a new user — they become viewer automatically
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "assignee@example.com", "name": "Assignee", "password": "Passw0rd!secure"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user"]


async def _create_incident(client: AsyncClient, token: str, assignee_id: str | None = None) -> dict:
    payload = {
        "title": "Database timeout",
        "description": "Connection pool exhausted under load",
        "severity": "high",
        "source": "monitor",
    }
    if assignee_id:
        payload["assignee_id"] = assignee_id
    resp = await client.post("/api/v1/incidents", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_T07_creating_incident_with_assignee_sends_notification(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T07: Creating an incident with an assignee_id must produce one Notification row."""
    token = await _admin_token(client)
    assignee = await _create_assignee(client, token)

    await _create_incident(client, token, assignee_id=assignee["id"])

    result = await db_session.execute(
        select(Notification).where(Notification.user_id == assignee["id"])
    )
    notifications = result.scalars().all()
    assert len(notifications) == 1, f"Expected 1 notification, got {len(notifications)}"
    assert "assigned" in notifications[0].title.lower()


@pytest.mark.asyncio
async def test_T08_updating_assignee_sends_notification_to_new_assignee(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T08: Patching assignee_id to a new user must send exactly one notification to that user."""
    token = await _admin_token(client)
    assignee = await _create_assignee(client, token)

    incident = await _create_incident(client, token)  # no assignee initially

    resp = await client.patch(
        f"/api/v1/incidents/{incident['id']}",
        json={"assignee_id": assignee["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    result = await db_session.execute(
        select(Notification).where(Notification.user_id == assignee["id"])
    )
    notifications = result.scalars().all()
    assert len(notifications) == 1, (
        f"Expected 1 reassignment notification, got {len(notifications)}"
    )


@pytest.mark.asyncio
async def test_T09_updating_other_fields_sends_no_notification(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T09: Patching severity or status (no assignee_id change) must not create a Notification."""
    token = await _admin_token(client)
    incident = await _create_incident(client, token)

    resp = await client.patch(
        f"/api/v1/incidents/{incident['id']}",
        json={"severity": "critical"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    result = await db_session.execute(select(Notification))
    notifications = result.scalars().all()
    assert len(notifications) == 0, (
        f"Expected 0 notifications for non-assignee update, got {len(notifications)}"
    )


@pytest.mark.asyncio
async def test_T10_soft_deleted_incident_not_returned_in_list(
    client: AsyncClient,
) -> None:
    """T10: After DELETE /incidents/{id}, the incident must not appear in GET /incidents."""
    token = await _admin_token(client)
    incident = await _create_incident(client, token)

    del_resp = await client.delete(
        f"/api/v1/incidents/{incident['id']}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204, del_resp.text

    list_resp = await client.get("/api/v1/incidents", headers=auth_headers(token))
    assert list_resp.status_code == 200, list_resp.text
    ids = [i["id"] for i in list_resp.json()["items"]]
    assert incident["id"] not in ids, "Soft-deleted incident must not appear in list"


def test_T11_invalid_sort_value_returns_422() -> None:
    """T11: IncidentFilters must reject unknown sort values with a ValidationError."""
    import pytest as _pytest
    from pydantic import ValidationError
    from app.schemas.incidents import IncidentFilters

    with _pytest.raises(ValidationError) as exc_info:
        IncidentFilters(sort="injected")

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("sort",) for e in errors), (
        f"Expected error on 'sort' field, got: {errors}"
    )
    assert any("injected" in str(e["msg"]) or "Invalid sort" in str(e["msg"]) for e in errors)


def test_T12_tag_longer_than_64_chars_returns_422() -> None:
    """T12: IncidentCreate must reject tags longer than 64 characters with a ValidationError."""
    import pytest as _pytest
    from pydantic import ValidationError
    from app.schemas.incidents import IncidentCreate

    with _pytest.raises(ValidationError) as exc_info:
        IncidentCreate(
            title="Tag test",
            description="Testing tag length validation",
            severity="low",
            tags=["a" * 65],
        )

    errors = exc_info.value.errors()
    assert any("tags" in str(e["loc"]) for e in errors), (
        f"Expected error on 'tags' field, got: {errors}"
    )


def test_T13_list_of_21_tags_returns_422() -> None:
    """T13: IncidentCreate must reject lists of more than 20 tags with a ValidationError."""
    import pytest as _pytest
    from pydantic import ValidationError
    from app.schemas.incidents import IncidentCreate

    with _pytest.raises(ValidationError) as exc_info:
        IncidentCreate(
            title="Too many tags",
            description="Testing maximum tag count constraint",
            severity="low",
            tags=[f"tag{i}" for i in range(21)],
        )

    errors = exc_info.value.errors()
    assert any("tags" in str(e["loc"]) for e in errors), (
        f"Expected error on 'tags' field, got: {errors}"
    )
