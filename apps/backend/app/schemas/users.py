from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Role | None = None
    is_active: bool | None = None

