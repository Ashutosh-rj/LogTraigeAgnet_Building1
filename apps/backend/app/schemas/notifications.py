from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    incident_id: str | None = None
    title: str
    message: str
    kind: str
    read_at: datetime | None = None
    notification_metadata: dict
    created_at: datetime
    updated_at: datetime

