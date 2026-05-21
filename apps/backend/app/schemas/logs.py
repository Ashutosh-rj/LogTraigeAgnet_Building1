from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import LogLevel


class LogCreate(BaseModel):
    level: LogLevel
    message: str = Field(min_length=1, max_length=10000)
    source: str = Field(min_length=1, max_length=160)
    observed_at: datetime | None = None
    attributes: dict = Field(default_factory=dict)


class LogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    level: LogLevel
    message: str
    source: str
    observed_at: datetime
    attributes: dict
    created_at: datetime
    updated_at: datetime

