"""Price list and product templates, managed by admins.

A product's price comes from its components (the template). Each component is one material or
one labour rate, multiplied by a measurement of the opening:

    quantity = basis_value(width, height) * factor * (1 + waste_percent / 100)
    cost     = quantity * unit_price

Basis values: area (m²), perimeter / width / height (m), fixed (1 per product unit).
"""

import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum


class PriceUnit(StrEnum):
    SQM = "sqm"  # per square metre
    LM = "lm"  # per linear metre
    PIECE = "piece"  # per piece / per job


class MaterialCategory(StrEnum):
    GLASS = "glass"
    ALUMINUM = "aluminum"
    METAL = "metal"
    HARDWARE = "hardware"
    OTHER = "other"


class ProductCategory(StrEnum):
    SLIDING_WINDOW = "sliding_window"
    SLIDING_DOOR = "sliding_door"
    WINDOW_GRILL = "window_grill"
    OTHER = "other"


class Basis(StrEnum):
    AREA = "area"
    PERIMETER = "perimeter"
    WIDTH = "width"
    HEIGHT = "height"
    FIXED = "fixed"


# Which measurement fits which price unit (m² with area, metres with lengths, pieces with fixed).
BASIS_UNIT = {
    Basis.AREA: PriceUnit.SQM,
    Basis.PERIMETER: PriceUnit.LM,
    Basis.WIDTH: PriceUnit.LM,
    Basis.HEIGHT: PriceUnit.LM,
    Basis.FIXED: PriceUnit.PIECE,
}

Money = Numeric(12, 2)
Percent = Numeric(5, 2)


class Material(UUIDPk, Timestamps, Base):
    __tablename__ = "materials"
    __table_args__ = (CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),)

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[MaterialCategory] = mapped_column(str_enum(MaterialCategory, "category"))
    unit: Mapped[PriceUnit] = mapped_column(str_enum(PriceUnit, "unit"))
    unit_price: Mapped[Decimal] = mapped_column(Money)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)


class LaborRate(UUIDPk, Timestamps, Base):
    __tablename__ = "labor_rates"
    __table_args__ = (CheckConstraint("rate >= 0", name="rate_nonnegative"),)

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[PriceUnit] = mapped_column(str_enum(PriceUnit, "unit"))
    rate: Mapped[Decimal] = mapped_column(Money)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)


class Product(UUIDPk, Timestamps, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("min_width_mm > 0 AND min_width_mm <= max_width_mm", name="width_range"),
        CheckConstraint(
            "min_height_mm > 0 AND min_height_mm <= max_height_mm", name="height_range"
        ),
    )

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[ProductCategory] = mapped_column(str_enum(ProductCategory, "category"))
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    min_width_mm: Mapped[int] = mapped_column(Integer)
    max_width_mm: Mapped[int] = mapped_column(Integer)
    min_height_mm: Mapped[int] = mapped_column(Integer)
    max_height_mm: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)


class ProductComponent(UUIDPk, Timestamps, Base):
    """One line of a product template: a material OR a labour rate, never both."""

    __tablename__ = "product_components"
    __table_args__ = (
        CheckConstraint(
            "(material_id IS NULL) <> (labor_rate_id IS NULL)", name="material_xor_labor"
        ),
        CheckConstraint("factor > 0", name="factor_positive"),
        CheckConstraint("waste_percent >= 0 AND waste_percent <= 100", name="waste_range"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    labor_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("labor_rates.id"), index=True
    )
    basis: Mapped[Basis] = mapped_column(str_enum(Basis, "basis"))
    factor: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    waste_percent: Mapped[Decimal] = mapped_column(Percent, server_default="0", default=Decimal(0))
    label: Mapped[str] = mapped_column(String(120), server_default="", default="")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", default=0)


class PricingSettings(Timestamps, Base):
    """Single row (id = 1) with shop-wide pricing settings."""

    __tablename__ = "pricing_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("markup_percent >= 0 AND markup_percent <= 500", name="markup_range"),
        CheckConstraint("vat_percent >= 0 AND vat_percent <= 100", name="vat_range"),
        CheckConstraint("quote_validity_days BETWEEN 1 AND 365", name="validity_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    markup_percent: Mapped[Decimal] = mapped_column(Percent)
    vat_percent: Mapped[Decimal] = mapped_column(Percent)
    currency: Mapped[str] = mapped_column(String(3))

    # Quotation / PDF settings (migration 0003)
    quote_validity_days: Mapped[int] = mapped_column(Integer, server_default="30")
    business_name: Mapped[str] = mapped_column(String(120), server_default="")
    business_address: Mapped[str] = mapped_column(String(300), server_default="")
    business_contact: Mapped[str] = mapped_column(String(120), server_default="")
    quote_terms: Mapped[str] = mapped_column(Text, server_default="")
