from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TriageReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    summary: str
    root_cause: str
    recommendations: list[str]
    confidence: float = Field(ge=0, le=1)
    model_version: str
    created_at: datetime
    updated_at: datetime

