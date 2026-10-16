from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DayPoint(BaseModel):
    day: date  # Philippine date the quotation was requested
    approved: int
    approved_value: Decimal


class GroupRow(BaseModel):
    label: str
    approved: int
    approved_value: Decimal


class ProjectRow(BaseModel):
    id: str
    number: str | None
    customer_name: str
    product_name: str
    city: str
    total: Decimal
    created_at: str


class DashboardOut(BaseModel):
    """Approved quotations only, requested within [date_from, date_to] (Philippine dates).

    Two exceptions: the approval rate also needs the rejected count, and `pending_now` counts
    every request still waiting for review. Deleted quotations never count.
    """

    date_from: date
    date_to: date
    currency: str
    approved: int
    approved_value: Decimal
    average_value: Decimal | None  # approved_value / approved; None if nothing approved
    rejected: int
    approval_rate: Decimal | None  # approved / (approved + rejected), percent; None if no reviews
    pending_now: int  # all pending requests, regardless of date
    per_day: list[DayPoint]
    by_location: list[GroupRow]
    by_product: list[GroupRow]
    top_projects: list[ProjectRow]
