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

from app.models import Basis, MaterialCategory, PriceUnit, ProductCategory
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


class MaterialIn(_In):
    code: Code
    name: Name
    category: MaterialCategory
    unit: PriceUnit
    unit_price: Price


class MaterialUpdate(_In):
    code: Code | None = None
    name: Name | None = None
    category: MaterialCategory | None = None
    unit: PriceUnit | None = None
    unit_price: Price | None = None
    is_active: bool | None = None


class MaterialOut(_Out):
    id: uuid.UUID
    code: str
    name: str
    category: MaterialCategory
    unit: PriceUnit
    unit_price: Decimal
    is_active: bool
    updated_at: datetime


# ---------- labour rates ----------


class LaborRateIn(_In):
    code: Code
    name: Name
    unit: PriceUnit
    rate: Price


class LaborRateUpdate(_In):
    code: Code | None = None
    name: Name | None = None
    unit: PriceUnit | None = None
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


class OptionUpdate(_In):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    width_reduction_mm: Reduction | None = None
    height_reduction_mm: Reduction | None = None


class OptionOut(_Out):
    id: uuid.UUID
    group_id: uuid.UUID | None
    name: str
    description: str
    sort_order: int
    width_reduction_mm: int
    height_reduction_mm: int


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
    kind: str
    code: str
    name: str
    label: str
    basis: Basis
    unit: PriceUnit
    unit_price: Decimal
    quantity: Decimal
    cost: Decimal
    option: str = ""  # add-on name; "" = always included (and in snapshots before add-ons)
    width_mm: int | None = None  # size this line was measured at (None in older snapshots)
    height_mm: int | None = None


class PricePreviewOut(BaseModel):
    width_mm: int
    height_mm: int
    quantity: int
    lines: list[PriceLineOut]
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
    currency: str
    warnings: list[str]
