"""Admin catalogue schemas. Money and quantities are Decimal (serialised as strings in JSON)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from app.models import Basis, MaterialCategory, PriceUnit, PricingMethod, ProductCategory
from app.models.catalog import StockUnit
from app.schemas.common import OptionalPersonName


def _upper(v: object) -> object:
    return v.strip().upper() if isinstance(v, str) else v


Code = Annotated[str, BeforeValidator(_upper), Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,29}$")]
Name = Annotated[str, Field(min_length=2, max_length=120)]
Price = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Factor = Annotated[Decimal, Field(gt=0, le=1000, max_digits=10, decimal_places=4)]
Millimetres = Annotated[int, Field(ge=1, le=20_000)]


def _unique_ids(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    if len(set(ids)) != len(ids):
        raise ValueError("each add-on can be chosen once")
    return ids


# Chosen add-ons of the product (max 10, no repeats).
OptionIds = Annotated[list[uuid.UUID], Field(max_length=10), AfterValidator(_unique_ids)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- materials ----------

# Bars: the length one bar is sold in (21 ft, 6 m). Only for unit "bar".
StockLength = Annotated[Decimal, Field(gt=0, le=1000, max_digits=8, decimal_places=2)]
# Labour is paid per piece (job), per foot or per sq ft; never per kilo or per bar.
LaborUnit = Literal["piece", "ft", "sqft"]


def check_stock_length(
    unit: PriceUnit, length: Decimal | None, length_unit: StockUnit | None
) -> None:
    if unit == PriceUnit.BAR and (length is None or length_unit is None):
        raise ValueError("a bar needs its length, e.g. 21 ft or 6 m")
    if unit != PriceUnit.BAR and (length is not None or length_unit is not None):
        raise ValueError("only items sold per bar have a bar length")


class MaterialIn(_In):
    code: Code
    name: Name
    category: MaterialCategory
    unit: PriceUnit
    unit_price: Price  # bars: price of one whole bar
    stock_length: StockLength | None = None
    stock_length_unit: StockUnit | None = None

    @model_validator(mode="after")
    def bar_length(self) -> Self:
        check_stock_length(self.unit, self.stock_length, self.stock_length_unit)
        return self


class MaterialUpdate(_In):
    """Bar length: send it with (or after) unit "bar"; changing to another unit clears it."""

    code: Code | None = None
    name: Name | None = None
    category: MaterialCategory | None = None
    unit: PriceUnit | None = None
    unit_price: Price | None = None
    stock_length: StockLength | None = None
    stock_length_unit: StockUnit | None = None
    is_active: bool | None = None


class MaterialOut(_Out):
    id: uuid.UUID
    code: str
    name: str
    category: MaterialCategory
    unit: PriceUnit
    unit_price: Decimal
    stock_length: Decimal | None
    stock_length_unit: str | None
    is_active: bool
    updated_at: datetime


# ---------- labour rates ----------


class LaborRateIn(_In):
    code: Code
    name: Name
    unit: LaborUnit
    rate: Price


class LaborRateUpdate(_In):
    code: Code | None = None
    name: Name | None = None
    unit: LaborUnit | None = None
    rate: Price | None = None
    is_active: bool | None = None


class LaborRateOut(_Out):
    id: uuid.UUID
    code: str
    name: str
    unit: PriceUnit
    rate: Decimal
    is_active: bool
    updated_at: datetime


# ---------- products ----------


class ProductIn(_In):
    code: Code
    name: Name
    category: ProductCategory
    description: str = Field(default="", max_length=2000)
    min_width_mm: Millimetres
    max_width_mm: Millimetres
    min_height_mm: Millimetres
    max_height_mm: Millimetres
    # per_sqft: sold at rate_per_sqft (+ chosen options' rates), VAT included; the template is a
    # cost guide. computed: priced from the template lines + markup.
    pricing_method: PricingMethod = PricingMethod.COMPUTED
    rate_per_sqft: Price = Decimal(0)

    @model_validator(mode="after")
    def ranges(self) -> Self:
        if self.min_width_mm > self.max_width_mm or self.min_height_mm > self.max_height_mm:
            raise ValueError("minimum size must not exceed maximum size")
        return self


class ProductUpdate(_In):
    code: Code | None = None
    name: Name | None = None
    category: ProductCategory | None = None
    description: str | None = Field(default=None, max_length=2000)
    min_width_mm: Millimetres | None = None
    max_width_mm: Millimetres | None = None
    min_height_mm: Millimetres | None = None
    max_height_mm: Millimetres | None = None
    pricing_method: PricingMethod | None = None
    rate_per_sqft: Price | None = None
    is_active: bool | None = None


class ProductOut(_Out):
    id: uuid.UUID
    code: str
    name: str
    category: ProductCategory
    description: str
    min_width_mm: int
    max_width_mm: int
    min_height_mm: int
    max_height_mm: int
    pricing_method: PricingMethod
    rate_per_sqft: Decimal
    is_active: bool
    updated_at: datetime


# ---------- options: add-ons and choose-one groups (e.g. Glass type) ----------

# How much smaller the rest of the window is measured when an option is chosen (e.g. open back).
Reduction = Annotated[int, Field(ge=0, le=2000)]


class OptionGroupIn(_In):
    name: str = Field(min_length=2, max_length=80)
    sort_order: int = Field(default=0, ge=0, le=1000)


class OptionGroupUpdate(_In):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    sort_order: int | None = Field(default=None, ge=0, le=1000)


class OptionGroupOut(_Out):
    id: uuid.UUID
    name: str
    sort_order: int


class OptionIn(_In):
    group_id: uuid.UUID | None = None  # None = add-on; else a choice of that group
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    sort_order: int = Field(default=0, ge=0, le=1000)
    width_reduction_mm: Reduction = 0
    height_reduction_mm: Reduction = 0
    rate_per_sqft: Price = Decimal(0)  # per-sq-ft products: added to the rate when chosen


class OptionUpdate(_In):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    width_reduction_mm: Reduction | None = None
    height_reduction_mm: Reduction | None = None
    rate_per_sqft: Price | None = None


class OptionOut(_Out):
    id: uuid.UUID
    group_id: uuid.UUID | None
    name: str
    description: str
    sort_order: int
    width_reduction_mm: int
    height_reduction_mm: int
    rate_per_sqft: Decimal


class ComponentIn(_In):
    material_id: uuid.UUID | None = None
    labor_rate_id: uuid.UUID | None = None
    option_id: uuid.UUID | None = None  # None = always included
    basis: Basis
    factor: Factor
    waste_percent: Percent = Decimal(0)
    label: str = Field(default="", max_length=120)
    sort_order: int = Field(default=0, ge=0, le=1000)

    @model_validator(mode="after")
    def exactly_one_item(self) -> Self:
        if (self.material_id is None) == (self.labor_rate_id is None):
            raise ValueError("choose either a material or a labour rate")
        return self


class ComponentUpdate(_In):
    # Sent as null: move the line to "always included". Left out: unchanged.
    option_id: uuid.UUID | None = None
    basis: Basis | None = None
    factor: Factor | None = None
    waste_percent: Percent | None = None
    label: str | None = Field(default=None, max_length=120)
    sort_order: int | None = Field(default=None, ge=0, le=1000)


class ComponentOut(BaseModel):
    id: uuid.UUID
    kind: Literal["material", "labor"]
    material_id: uuid.UUID | None
    labor_rate_id: uuid.UUID | None
    option_id: uuid.UUID | None
    item_code: str
    item_name: str
    item_unit: PriceUnit
    item_price: Decimal
    item_stock_length: Decimal | None = None
    item_stock_length_unit: str | None = None
    item_active: bool
    basis: Basis
    factor: Decimal
    waste_percent: Decimal
    label: str
    sort_order: int


class ProductDetailOut(ProductOut):
    option_groups: list[OptionGroupOut]
    options: list[OptionOut]
    components: list[ComponentOut]


# ---------- pricing settings & preview ----------


class PricingSettingsIn(_In):
    markup_percent: Annotated[Decimal, Field(ge=0, le=500, max_digits=5, decimal_places=2)]
    vat_percent: Percent
    currency: Annotated[str, BeforeValidator(_upper), Field(pattern=r"^[A-Z]{3}$")]
    quote_validity_days: int = Field(ge=1, le=365)
    business_name: str = Field(min_length=2, max_length=120)
    # Required (may be empty strings): PUT replaces everything, so a client that forgets a
    # field must get a 422 instead of silently erasing it.
    business_address: str = Field(max_length=300)
    business_contact: str = Field(max_length=120)
    quote_terms: str = Field(max_length=4000)
    # Totals round up to a multiple of this (100: 21,423 -> 21,500); 0 turns rounding off.
    rounding_step: Annotated[Decimal, Field(ge=0, le=100_000, max_digits=8, decimal_places=2)]
    owner_name: OptionalPersonName  # printed under the owner's signature line


class PricingSettingsOut(_Out):
    markup_percent: Decimal
    vat_percent: Decimal
    currency: str
    quote_validity_days: int
    business_name: str
    business_address: str
    business_contact: str
    quote_terms: str
    rounding_step: Decimal
    owner_name: str
    updated_at: datetime


class PricePreviewIn(_In):
    width: Annotated[Decimal, Field(gt=0, le=10_000, max_digits=8, decimal_places=2)]
    height: Annotated[Decimal, Field(gt=0, le=10_000, max_digits=8, decimal_places=2)]
    unit: Literal["cm", "in"]
    quantity: int = Field(default=1, ge=1, le=100)
    option_ids: OptionIds = []


class PriceLineOut(BaseModel):
    """Also reads stored snapshots: before v2, units were "sqm"/"lm" and sizes in mm."""

    kind: str
    code: str
    name: str
    label: str
    basis: Basis
    unit: str
    unit_price: Decimal
    quantity: Decimal
    cost: Decimal
    option: str = ""  # add-on name; "" = always included (and in snapshots before add-ons)
    needed: Decimal | None = None  # bars: before rounding up to whole bars
    stock_length: Decimal | None = None
    stock_length_unit: str | None = None
    width_in: Decimal | None = None  # size this line was measured at (v2)
    height_in: Decimal | None = None
    width_mm: int | None = None  # ... in snapshots between add-ons and v2
    height_mm: int | None = None


class RateLineOut(BaseModel):
    name: str
    rate_per_sqft: Decimal


class PricePreviewOut(BaseModel):
    """A price breakdown (preview, or an item's stored snapshot). v2 fields are None before v2."""

    pricing_method: PricingMethod | None = None  # None: priced before v2 (VAT added on top)
    width_mm: int
    height_mm: int
    width_in: Decimal | None = None
    height_in: Decimal | None = None
    area_sqft: Decimal | None = None
    quantity: int
    lines: list[PriceLineOut]
    rates: list[RateLineOut] = []
    rate_per_sqft: Decimal | None = None
    unit_subtotal: Decimal
    unit_price: Decimal
    subtotal: Decimal
    markup_percent: Decimal
    markup: Decimal
    net: Decimal
    vat_percent: Decimal
    vat: Decimal
    total: Decimal
    rounding_step: Decimal
    rounding: Decimal
    rounded_total: Decimal
    vat_included: Decimal | None = None
    margin: Decimal | None = None
    currency: str
    warnings: list[str]


class RaiseRatesIn(_In):
    """Raise (or lower) every per-sq-ft rate: products' own rates and their options' extras."""

    percent: Annotated[Decimal, Field(ge=-50, le=100, max_digits=5, decimal_places=2)]

    @model_validator(mode="after")
    def not_zero(self) -> Self:
        if self.percent == 0:
            raise ValueError("percent must not be 0")
        return self


class RaiseRatesOut(BaseModel):
    products: int
    options: int
