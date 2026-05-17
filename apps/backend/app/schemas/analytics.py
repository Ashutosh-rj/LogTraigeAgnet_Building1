from __future__ import annotations

from pydantic import BaseModel


class IncidentAnalytics(BaseModel):
    total: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    open_critical: int
    mean_time_to_resolve_hours: float | None

