from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


class LogCitation(BaseModel):
    chunk_index: int
    log_line_exact: str = Field(..., description="EXACT substring from the log. Do not paraphrase.")
    timestamp: str


class RootCause(BaseModel):
    service: str
    failure_category: Literal["database_timeout", "oom_killed", "network_partition", "unknown"]
    description: str
    citations: List[LogCitation] = Field(min_length=1)


class TriageReportSchema(BaseModel):
    incident_id: str
    summary: str
    root_causes: List[RootCause]
    recommendations: List[str]
    confidence: float = Field(ge=0.1, le=0.95)


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

