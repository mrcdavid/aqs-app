"""Customer quotation requests.

Prices are frozen in `snapshot` when the customer clicks Process, so later catalogue changes never
alter an existing quotation. Columns used by the dashboard (total, city, province, status,
created_at) are copied out of the snapshot for easy querying.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum


class QuotationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Quotation(UUIDPk, Timestamps, Base):
    __tablename__ = "quotations"
    __table_args__ = (
        CheckConstraint(
            "status <> 'approved' OR (number IS NOT NULL AND reviewed_at IS NOT NULL"
            " AND valid_until IS NOT NULL)",
            name="approved_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' OR (reviewed_at IS NOT NULL AND review_note IS NOT NULL)",
            name="rejected_fields",
        ),
        CheckConstraint("input_unit IN ('cm', 'in')", name="input_unit"),
        CheckConstraint("quantity BETWEEN 1 AND 100", name="quantity_range"),
        CheckConstraint("width_mm > 0 AND height_mm > 0", name="size_positive"),
        Index("ix_quotations_created_at", "created_at"),
    )

    # Assigned on approval: AQS-2026-000123
    number: Mapped[str | None] = mapped_column(String(20), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    status: Mapped[QuotationStatus] = mapped_column(str_enum(QuotationStatus, "status"), index=True)

    # What the customer typed, and the same in millimetres.
    input_width: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    input_height: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    input_unit: Mapped[str] = mapped_column(String(2))
    width_mm: Mapped[int] = mapped_column(Integer)
    height_mm: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)

    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    customer_city: Mapped[str] = mapped_column(String(80))
    customer_province: Mapped[str] = mapped_column(String(80))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    valid_until: Mapped[date | None] = mapped_column(Date)
    pdf_file: Mapped[str | None] = mapped_column(String(64))


class QuoteCounter(Base):
    """Next quote number per year, incremented atomically on approval."""

    __tablename__ = "quote_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_number: Mapped[int] = mapped_column(Integer)
