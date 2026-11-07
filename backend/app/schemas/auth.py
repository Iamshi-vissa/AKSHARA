from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import ApiModel


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def _password_rules(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("password must not start or end with whitespace")
        if not any(c.isalpha() for c in v) or not any(not c.isalpha() for c in v):
            raise ValueError("password must contain letters and at least one digit or symbol")
        return v


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    preferred_unit: str
    allow_external_llm: bool
    created_at: datetime


class UserUpdate(ApiModel):
    display_name: str | None = Field(default=None, max_length=120)
    preferred_unit: Literal["pt", "mm", "in"] | None = None
    allow_external_llm: bool | None = None
