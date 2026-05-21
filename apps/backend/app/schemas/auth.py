from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.users import UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        has_upper = any(char.isupper() for char in value)
        has_lower = any(char.islower() for char in value)
        has_digit = any(char.isdigit() for char in value)
        if not (has_upper and has_lower and has_digit):
            raise ValueError("Password must contain uppercase, lowercase, and numeric characters")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
