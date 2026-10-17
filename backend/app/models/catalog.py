"""Price list and product templates, managed by admins (pricing v2, see docs/quotations.md).

Materials and labour are priced in the units the shop buys them in: per piece, per kilo, per foot,
per sq ft, or per **bar** of a stock length (e.g. a 21-ft profile or a 6-m square bar; always
counted as whole bars). A product's template lines measure the opening in feet / sq ft:

    quantity = basis_value(width, height) * factor * (1 + waste_percent / 100)
    cost     = quantity * unit_price          (bars: whole bars, rounded up)

Basis values: area (sq ft), perimeter / width / height (ft), fixed (1 per product unit).

A product is sold either **per sq ft** (owner-set rate: the product's base rate plus the chosen
options' rates, e.g. a glass type and an open back extra; the template is then only a cost guide)
or **computed** from its template (line costs + markup, e.g. grills).

Lines without an option are always included. Lines that belong to a ProductOption are only
priced when that option is chosen. An option is either:
  - an add-on (no group), ticked or not, e.g. "Open back (outer jamb)";
  - a choice in a ProductOptionGroup, where exactly one must be chosen, e.g. Glass type:
    "Ordinary" or "Reflective".
An option may make the window smaller (width/height_reduction_mm): the size typed is then the wall
opening, the option's own lines use it as is, and every other line is measured that much smaller.
"""

import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum


class PriceUnit(StrEnum):
    PIECE = "piece"  # per piece / per job
    KG = "kg"  # per kilo (e.g. jamb rubber, vinyl)
    FT = "ft"  # per foot
    SQFT = "sqft"  # per square foot (e.g. glass)
    BAR = "bar"  # per bar of `stock_length` (e.g. 21-ft profile, 6-m square bar); whole bars


class StockUnit(StrEnum):
    FT = "ft"
    M = "m"


class PricingMethod(StrEnum):
    PER_SQFT = "per_sqft"  # sold per sq ft at owner-set rates (template = cost guide)
    COMPUTED = "computed"  # template line costs + markup (e.g. grills)


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


LENGTHS = (Basis.PERIMETER, Basis.WIDTH, Basis.HEIGHT)
# Which measurements make sense for each unit. Bars: a length (feet needed ÷ stock length), an
# area (factor = bars per sq ft, e.g. grills) or a fixed number of bars.
BASES_FOR_UNIT: dict[PriceUnit, tuple[Basis, ...]] = {
    PriceUnit.PIECE: (Basis.FIXED,),
    PriceUnit.KG: (*LENGTHS, Basis.AREA, Basis.FIXED),
    PriceUnit.FT: LENGTHS,
    PriceUnit.SQFT: (Basis.AREA,),
    PriceUnit.BAR: (*LENGTHS, Basis.AREA, Basis.FIXED),
}
LABOR_UNITS = (PriceUnit.PIECE, PriceUnit.FT, PriceUnit.SQFT)

Money = Numeric(12, 2)
Percent = Numeric(5, 2)


class Material(UUIDPk, Timestamps, Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
        CheckConstraint("stock_length_unit IN ('ft', 'm')", name="stock_length_unit"),
        CheckConstraint(
            "(unit = 'bar') = (stock_length IS NOT NULL AND stock_length > 0"
            " AND stock_length_unit IS NOT NULL)",
            name="bar_stock_length",
        ),
    )

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[MaterialCategory] = mapped_column(str_enum(MaterialCategory, "category"))
    unit: Mapped[PriceUnit] = mapped_column(str_enum(PriceUnit, "unit"))
    unit_price: Mapped[Decimal] = mapped_column(Money)  # per unit; for bars, per whole bar
    # Bars only: the length one bar is sold in, e.g. 21 ft or 6 m.
    stock_length: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    stock_length_unit: Mapped[str | None] = mapped_column(String(2))
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
        CheckConstraint("rate_per_sqft >= 0", name="rate_per_sqft_nonnegative"),
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
    pricing_method: Mapped[PricingMethod] = mapped_column(
        str_enum(PricingMethod, "pricing_method"),
        server_default=PricingMethod.COMPUTED.value,
        default=PricingMethod.COMPUTED,
    )
    # Per-sq-ft products: base selling rate (VAT included), plus the chosen options' rates.
    rate_per_sqft: Mapped[Decimal] = mapped_column(Money, server_default="0", default=Decimal(0))


class ProductOptionGroup(UUIDPk, Timestamps, Base):
    """A "choose exactly one" question of a product (e.g. Glass type); its options are choices."""

    __tablename__ = "product_option_groups"
    __table_args__ = (UniqueConstraint("product_id", "name"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", default=0)


class ProductOption(UUIDPk, Timestamps, Base):
    """An add-on (group_id None) or one choice of a group, made of template lines."""

    __tablename__ = "product_options"
    __table_args__ = (
        UniqueConstraint("product_id", "group_id", "name"),
        CheckConstraint(
            "width_reduction_mm BETWEEN 0 AND 2000 AND height_reduction_mm BETWEEN 0 AND 2000",
            name="reduction_range",
        ),
        CheckConstraint("rate_per_sqft >= 0", name="rate_per_sqft_nonnegative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    # None = add-on (tick or not); else one choice of this group. Deleting the group deletes it.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_option_groups.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), server_default="", default="")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    # When chosen, every other line is measured this much narrower / shorter (see module doc).
    width_reduction_mm: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    height_reduction_mm: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    # Per-sq-ft products: added to the selling rate when chosen (glass type rate, open back extra).
    rate_per_sqft: Mapped[Decimal] = mapped_column(Money, server_default="0", default=Decimal(0))


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
    # None = always included; else only priced when this add-on is chosen. Deleting the add-on
    # deletes its lines (quotations keep their own copy in the snapshot).
    option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_options.id", ondelete="CASCADE"), index=True
    )


class PricingSettings(Timestamps, Base):
    """Single row (id = 1) with shop-wide pricing settings."""

    __tablename__ = "pricing_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("markup_percent >= 0 AND markup_percent <= 500", name="markup_range"),
        CheckConstraint("vat_percent >= 0 AND vat_percent <= 100", name="vat_range"),
        CheckConstraint("quote_validity_days BETWEEN 1 AND 365", name="validity_range"),
        CheckConstraint(
            "rounding_step >= 0 AND rounding_step <= 100000", name="rounding_step_range"
        ),
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

    # Totals are rounded up to a multiple of this (0 = off); owner signs the PDF (migration 0004)
    rounding_step: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="100")
    owner_name: Mapped[str] = mapped_column(String(120), server_default="")
