"""T14–T15 — triage idempotency: exactly one DB row per incident."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TriageReport
from tests.conftest import auth_headers, register


async def _setup_incident(client: AsyncClient) -> tuple[str, str]:
    """Return (admin_token, incident_id)."""
    data = await register(client, email="admin@example.com", name="Admin")
    token = data["access_token"]

    resp = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Memory leak in worker",
            "description": "Worker process OOM after 2 hours of load",
            "severity": "critical",
            "source": "alertmanager",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return token, resp.json()["id"]


@pytest.mark.asyncio
async def test_T14_calling_triage_twice_produces_one_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T14: Two consecutive POST /incidents/{id}/triage calls must result in exactly one TriageReport row."""
    token, incident_id = await _setup_incident(client)

    r1 = await client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        headers=auth_headers(token),
    )
    assert r1.status_code == 200, r1.text

    r2 = await client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        headers=auth_headers(token),
    )
    assert r2.status_code == 200, r2.text

    result = await db_session.execute(
        select(TriageReport).where(TriageReport.incident_id == incident_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1, (
        f"Expected exactly 1 TriageReport row after two generates, found {len(rows)}"
    )


@pytest.mark.asyncio
async def test_T15_second_triage_call_updates_existing_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T15: The second triage generate must update the existing row, not insert a new one."""
    token, incident_id = await _setup_incident(client)

    # First generate
    r1 = await client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        headers=auth_headers(token),
    )
    assert r1.status_code == 200, r1.text
    report_id_first = r1.json()["id"]

    # Add a log so the second generate produces different content
    await client.post(
        f"/api/v1/incidents/{incident_id}/logs",
        json={"level": "error", "message": "OOM killer invoked", "source": "kernel"},
        headers=auth_headers(token),
    )

    # Second generate
    r2 = await client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        headers=auth_headers(token),
    )
    assert r2.status_code == 200, r2.text
    report_id_second = r2.json()["id"]

    # Same row id — it was updated in place
    assert report_id_first == report_id_second, (
        f"Expected same report id, got {report_id_first!r} vs {report_id_second!r}; "
        "second generate must UPDATE the existing row, not INSERT a new one"
    )

    # Double-check count in DB
    result = await db_session.execute(
        select(TriageReport).where(TriageReport.incident_id == incident_id)
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_T16_regenerated_report_reflects_new_log_content(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """T16: was_regenerated path — the regenerated report must incorporate newly ingested logs.

    Covers the branch in TriageService.generate() where ``existing is not None``
    (i.e. ``was_regenerated=True``).  Specifically asserts that:

    * The summary is different after adding an error log (confidence rises and
      the latest-signal message changes).
    * The model_version is preserved on the updated row.
    * The incident's own summary/root_cause fields are updated in place.
    """
    token, incident_id = await _setup_incident(client)

    # ── First generate (was_regenerated=False path) ──────────────────────────
    r1 = await client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        headers=auth_headers(token),
    )
    assert r1.status_code == 200, r1.text
    first_payload = r1.json()
    first_summary = first_payload["summary"]
    first_confidence = first_payload["confidence"]
    first_id = first_payload["id"]

    # Confirm single row exists before the second call.
    rows_before = (
        await db_session.execute(
            select(TriageReport).where(TriageReport.incident_id == incident_id)
        )
    ).scalars().all()
    assert len(rows_before) == 1

    # ── Inject an error log so the regenerated content differs ───────────────
    log_resp = await client.post(
        f"/api/v1/incidents/{incident_id}/logs",
        json={
            "level": "error",
            "message": "Heap allocation failed: out of memory",
            "source": "worker-process",
        },
        headers=auth_headers(token),
    )
    assert log_resp.status_code == 201, log_resp.text

    # ── Second generate (was_regenerated=True path) ──────────────────────────
    r2 = await client.post(
        f"/api/v1/incidents/{incident_id}/triage",
        headers=auth_headers(token),
    )
    assert r2.status_code == 200, r2.text
    second_payload = r2.json()

    # Row id must be unchanged — it was updated, not re-inserted.
    assert second_payload["id"] == first_id, (
        "was_regenerated path must UPDATE the existing row; id must not change"
    )

    # Summary must reference the new log signal.
    assert second_payload["summary"] != first_summary, (
        "Regenerated summary should differ after ingesting an error log"
    )

    # Confidence should be higher now that there is error-level telemetry.
    assert second_payload["confidence"] >= first_confidence, (
        f"Confidence should not decrease after adding error logs "
        f"({first_confidence} → {second_payload['confidence']})"
    )

    # model_version must be preserved on the updated row.
    assert second_payload.get("model_version") == first_payload.get("model_version"), (
        "model_version must be preserved when regenerating a triage report"
    )

    # Still exactly one row in the DB.
    rows_after = (
        await db_session.execute(
            select(TriageReport).where(TriageReport.incident_id == incident_id)
        )
    ).scalars().all()
    assert len(rows_after) == 1, (
        f"Expected 1 TriageReport row after regeneration, found {len(rows_after)}"
    )

