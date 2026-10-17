import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import MAX_ITEMS, ProductCategory, QuotationStatus
from app.schemas.catalog import OptionIds, PricePreviewOut
from app.schemas.common import OptionalEmail, PersonName, PhMobile, PlaceName

Size = Annotated[Decimal, Field(gt=0, le=10_000, max_digits=8, decimal_places=2)]
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class CatalogOptionOut(BaseModel):
    """An add-on that can be ticked when quoting this product."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str


class CatalogChoiceGroupOut(BaseModel):
    """A choose-one question, e.g. Glass type, with the choices that can be picked."""

    id: uuid.UUID
    name: str
    choices: list[CatalogOptionOut]


class CatalogProductOut(BaseModel):
    """What customers (and staff quoting walk-ins) see in the product picker."""

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
    choice_groups: list[CatalogChoiceGroupOut] = []  # pick exactly one in each
    options: list[CatalogOptionOut] = []  # add-ons, tick any


class QuotationItemIn(BaseModel):
    """One product of the request, with its size, quantity, choices and add-ons."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    width: Size
    height: Size
    unit: Literal["cm", "in"]
    quantity: int = Field(default=1, ge=1, le=100)
    option_ids: OptionIds = []  # the chosen add-ons plus one choice per group


class QuotationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QuotationItemIn] = Field(min_length=1, max_length=MAX_ITEMS)


class ClientIn(BaseModel):
    """A walk-in client's details, typed in by staff: same rules as a customer profile, minus
    age, plus an optional email."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: PersonName
    contact_number: PhMobile
    email: OptionalEmail = None
    address_line: str = Field(min_length=5, max_length=200)
    city: PlaceName
    province: PlaceName


class StaffQuotationIn(QuotationIn):
    """Staff quoting for a walk-in client: the same request plus the client's details."""

    client: ClientIn


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str = Field(default="", max_length=1000)
    # Approve only: replaces the quoted amount (e.g. 21,423 -> 21,500 by hand). None keeps it.
    final_total: Money | None = None


class CancelIn(BaseModel):
    """Staff withdrawing a pending request (e.g. the client changed their mind)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str = Field(default="", max_length=1000)  # optional reason, shown to the customer


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str = Field(min_length=3, max_length=1000)


class ItemSummaryOut(BaseModel):
    product_name: str
    input_width: Decimal
    input_height: Decimal
    input_unit: str
    width_mm: int
    height_mm: int
    quantity: int


class QuotationSummaryOut(BaseModel):
    id: uuid.UUID
    number: str | None
    status: QuotationStatus
    items: list[ItemSummaryOut]
    total: Decimal
    currency: str
    created_at: datetime


class AdminQuotationSummaryOut(QuotationSummaryOut):
    walk_in: bool
    customer_name: str
    customer_email: str
    customer_city: str
    customer_province: str


class ChoiceOut(BaseModel):
    group: str
    name: str


class QuotationItemOut(BaseModel):
    """One item as the customer sees it: its amount (VAT included), never costs or VAT."""

    position: int
    product_name: str
    product_description: str
    includes: list[str]
    choices: list[ChoiceOut]  # e.g. [{group: "Glass type", name: "Reflective"}]
    options: list[str]  # chosen add-ons, e.g. ["Open back aluminum"]
    input_width: Decimal
    input_height: Decimal
    input_unit: str
    width_mm: int
    height_mm: int
    area_sqft: Decimal | None  # per piece; None for quotations priced before v2
    quantity: int
    amount: Decimal  # for the whole quantity, VAT included, rounded up


class QuotationOut(BaseModel):
    """Customer view: an amount per item (VAT included), the total and the payment split. Never
    costs, markup, VAT or unit prices: what isn't sent can't be read in the browser either."""

    id: uuid.UUID
    number: str | None
    status: QuotationStatus
    items: list[QuotationItemOut]
    subtotal: Decimal  # sum of the item amounts
    adjustment: Decimal  # total - subtotal: an amount changed on approval (0 if none)
    total: Decimal
    downpayment: Decimal  # 50% before work starts
    balance: Decimal  # 50% on completion and installation
    currency: str
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None
    valid_until: date | None
    can_cancel: bool
    cancelled_by_staff: bool  # cancelled by the shop rather than by the customer


class AdminQuotationItemOut(QuotationItemOut):
    breakdown: PricePreviewOut  # full internal breakdown, including markup and VAT


class AdminQuotationOut(QuotationOut):
    items: list[AdminQuotationItemOut]  # type: ignore[assignment]  # adds each breakdown
    walk_in: bool
    customer: dict[str, Any]
    created_by_email: str | None
    reviewed_by_email: str | None
    total_adjusted: bool  # total differs from the sum of the item amounts
