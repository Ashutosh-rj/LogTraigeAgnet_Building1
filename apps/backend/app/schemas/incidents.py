from __future__ import annotations

from datetime import datetime
from typing import Annotated

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import IncidentStatus, Severity

# Individual tag must be non-empty and ≤ 64 characters.
TagStr = Annotated[str, Field(min_length=1, max_length=64)]

VALID_SORT_FIELDS = {
    "created_at", "-created_at",
    "updated_at", "-updated_at",
    "severity", "-severity",
    "status", "-status",
    "title", "-title",
}


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=5, max_length=5000)
    severity: Severity
    source: str = Field(default="manual", min_length=1, max_length=120)
    assignee_id: str | None = None
    tags: list[TagStr] = Field(default_factory=list, max_length=20)
    incident_metadata: dict = Field(default_factory=dict)

    @field_validator("title", "description", "source")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


# Sentinel object used to distinguish "field not sent" from "field explicitly
# set to null".  Pydantic's exclude_unset=True handles most cases, but for
# Optional[str] fields that share None as both default and a valid value
# (e.g. assignee_id=null to clear an assignee) we need a distinct default so
# model_fields_set is populated correctly when the client sends the field.
_UNSET: Any = object()


class IncidentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    description: str | None = Field(default=None, min_length=5, max_length=5000)
    severity: Severity | None = None
    status: IncidentStatus | None = None
    # Default is _UNSET (not None) so that model_fields_set reliably includes
    # "assignee_id" when the client explicitly sends null, and excludes it when
    # the field is simply omitted.  model_dump(exclude_unset=True) in
    # IncidentService.update() therefore behaves correctly in both cases.
    assignee_id: str | None = Field(default=_UNSET)
    tags: list[TagStr] | None = Field(default=None, max_length=20)
    incident_metadata: dict | None = None

    def model_post_init(self, __context: Any) -> None:
        # Normalise _UNSET back to None if assignee_id was never set,
        # so that downstream code only ever sees str | None.
        if self.assignee_id is _UNSET and "assignee_id" not in self.model_fields_set:
            object.__setattr__(self, "assignee_id", None)


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    source: str
    assignee_id: str | None = None
    created_by_id: str | None = None
    summary: str | None = None
    root_cause: str | None = None
    tags: list[str]
    incident_metadata: dict
    created_at: datetime
    updated_at: datetime


class IncidentFilters(BaseModel):
    status: IncidentStatus | None = None
    severity: Severity | None = None
    q: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort: str = Field(default="-created_at")

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, value: str) -> str:
        if value not in VALID_SORT_FIELDS:
            raise ValueError(
                f"Invalid sort value '{value}'. "
                f"Allowed values: {sorted(VALID_SORT_FIELDS)}"
            )
        return value
