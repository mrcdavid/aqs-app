import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import PASSWORD_MAX_LENGTH
from app.models import Role


class StaffLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    # No min length here: never tell an attacker which rule a guess broke.
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    has_profile: bool
