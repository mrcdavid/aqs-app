import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


STAFF_ROLES = frozenset({Role.ADMIN, Role.SUPER_ADMIN})


class AuthProvider(StrEnum):
    GOOGLE = "google"
    PASSWORD = "password"  # noqa: S105  (provider name, not a secret)


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        # Customers sign in with Google; staff sign in with a password. Never both.
        CheckConstraint(
            "(auth_provider = 'google' AND google_sub IS NOT NULL AND password_hash IS NULL"
            " AND role = 'user')"
            " OR (auth_provider = 'password' AND password_hash IS NOT NULL AND google_sub IS NULL"
            " AND role IN ('admin', 'super_admin'))",
            name="auth_fields",
        ),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)  # always lower-case
    role: Mapped[Role] = mapped_column(str_enum(Role, "role"))
    auth_provider: Mapped[AuthProvider] = mapped_column(str_enum(AuthProvider, "auth_provider"))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))

    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def can_log_in(self) -> bool:
        return self.is_active and self.deleted_at is None


class Profile(Timestamps, Base):
    __tablename__ = "profiles"
    __table_args__ = (CheckConstraint("age BETWEEN 18 AND 120", name="age_range"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(SmallInteger)
    contact_number: Mapped[str] = mapped_column(String(20))
    address_line: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80))
    province: Mapped[str] = mapped_column(String(80))
