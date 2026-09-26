import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import PASSWORD_MAX_LENGTH
from app.models import AuthProvider, Role

StaffRole = Literal["admin", "super_admin"]


class UserRowOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    auth_provider: AuthProvider
    full_name: str | None
    city: str | None
    is_active: bool
    deleted_at: datetime | None
    locked: bool
    last_login_at: datetime | None
    created_at: datetime
    active_sessions: int
    last_seen_at: datetime | None


class StaffCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    role: StaffRole
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    role: StaffRole | None = None


class PasswordResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class ActiveSessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: Role
    ip: str | None
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime
