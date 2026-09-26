import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ProductCategory, QuotationStatus
from app.schemas.catalog import PricePreviewOut

Size = Annotated[Decimal, Field(gt=0, le=10_000, max_digits=8, decimal_places=2)]


class CatalogProductOut(BaseModel):
    """What customers see in the product picker."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    category: ProductCategory
    description: str
    min_width_mm: int
    max_width_mm: int
    min_height_mm: int
    max_height_mm: int


class QuotationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    width: Size
    height: Size
    unit: Literal["cm", "in"]
    quantity: int = Field(default=1, ge=1, le=100)


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str = Field(default="", max_length=1000)


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str = Field(min_length=3, max_length=1000)


class QuotationSummaryOut(BaseModel):
    id: uuid.UUID
    number: str | None
    status: QuotationStatus
    product_name: str
    width_mm: int
    height_mm: int
    quantity: int
    total: Decimal
    currency: str
    created_at: datetime


class AdminQuotationSummaryOut(QuotationSummaryOut):
    customer_name: str
    customer_email: str
    customer_city: str
    customer_province: str


class QuotationOut(BaseModel):
    """Customer view: prices the customer pays, never internal costs or markup."""

    id: uuid.UUID
    number: str | None
    status: QuotationStatus
    product_name: str
    product_description: str
    includes: list[str]
    input_width: Decimal
    input_height: Decimal
    input_unit: str
    width_mm: int
    height_mm: int
    quantity: int
    unit_price: Decimal
    amount: Decimal
    vat_percent: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None
    valid_until: date | None
    can_cancel: bool


class AdminQuotationOut(QuotationOut):
    customer: dict[str, Any]
    reviewed_by_email: str | None
    breakdown: PricePreviewOut  # full internal breakdown, including markup
