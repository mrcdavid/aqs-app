"""Quotation requests: made by customers, or by staff for walk-in clients.

A quotation has one or more items (a product with its size, quantity, choices and add-ons). Each
item's prices are frozen in its own `snapshot` when Process is clicked, so later catalogue changes
never alter an existing quotation. The quotation's `snapshot` holds the client (and, once
approved, the business details). Columns used by the dashboard (total, city, province, status,
created_at, item product names and amounts) are copied out for easy querying.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, str_enum

MAX_ITEMS = 20  # per quotation


class QuotationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class QuotationItem(UUIDPk, Timestamps, Base):
    """One product of a quotation, with its own size, quantity and options."""

    __tablename__ = "quotation_items"
    __table_args__ = (
        UniqueConstraint("quotation_id", "position"),
        CheckConstraint("input_unit IN ('cm', 'in')", name="input_unit"),
        CheckConstraint("quantity BETWEEN 1 AND 100", name="quantity_range"),
        CheckConstraint("width_mm > 0 AND height_mm > 0", name="size_positive"),
    )

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)  # 0, 1, 2 ... in the order they were added
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(120))  # frozen, for the dashboard

    # What was typed, and the same in millimetres.
    input_width: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    input_height: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    input_unit: Mapped[str] = mapped_column(String(2))
    width_mm: Mapped[int] = mapped_column(Integer)
    height_mm: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)

    # This item's price for its whole quantity, VAT included and rounded up.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Frozen product, input, pricing breakdown, choices and add-ons.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)


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
        Index("ix_quotations_created_at", "created_at"),
    )

    # Assigned on approval: AQS-2026-000123
    number: Mapped[str | None] = mapped_column(String(20), unique=True)
    # The customer's account; None for a walk-in client quoted by staff (details in snapshot).
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    # Who made the request: the customer, or the staff member who quoted a walk-in client.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[QuotationStatus] = mapped_column(str_enum(QuotationStatus, "status"), index=True)

    # What the client pays (VAT included): the sum of the item amounts, or the amount set on
    # approval (the difference shows as an adjustment).
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
    # Deleted by a super admin: hidden from every list, page, PDF link and the dashboard, but kept
    # in the database (soft delete; the audit log records it too).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    # Always loaded with the quotation (one extra query), in the order they were added.
    items: Mapped[list[QuotationItem]] = relationship(
        order_by=QuotationItem.position, lazy="selectin", cascade="all, delete-orphan"
    )


class QuoteCounter(Base):
    """Next quote number per year, incremented atomically on approval."""

    __tablename__ = "quote_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_number: Mapped[int] = mapped_column(Integer)
