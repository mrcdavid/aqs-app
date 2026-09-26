"""Admin catalogue schemas. Money and quantities are Decimal (serialised as strings in JSON)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models import Basis, MaterialCategory, PriceUnit, ProductCategory


def _upper(v: object) -> object:
    return v.strip().upper() if isinstance(v, str) else v


Code = Annotated[str, BeforeValidator(_upper), Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,29}$")]
Name = Annotated[str, Field(min_length=2, max_length=120)]
Price = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Factor = Annotated[Decimal, Field(gt=0, le=1000, max_digits=10, decimal_places=4)]
Millimetres = Annotated[int, Field(ge=1, le=20_000)]


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


class ComponentIn(_In):
    material_id: uuid.UUID | None = None
    labor_rate_id: uuid.UUID | None = None
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


class PricingSettingsOut(_Out):
    markup_percent: Decimal
    vat_percent: Decimal
    currency: str
    quote_validity_days: int
    business_name: str
    business_address: str
    business_contact: str
    quote_terms: str
    updated_at: datetime


class PricePreviewIn(_In):
    width: Annotated[Decimal, Field(gt=0, le=10_000, max_digits=8, decimal_places=2)]
    height: Annotated[Decimal, Field(gt=0, le=10_000, max_digits=8, decimal_places=2)]
    unit: Literal["cm", "in"]
    quantity: int = Field(default=1, ge=1, le=100)


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
    currency: str
    warnings: list[str]
