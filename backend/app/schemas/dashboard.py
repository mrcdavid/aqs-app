from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DayPoint(BaseModel):
    day: date  # Philippine date
    requested: int
    approved: int
    approved_value: Decimal


class GroupRow(BaseModel):
    label: str
    requested: int
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
    """All figures count quotations *requested* within [date_from, date_to] (Philippine dates)."""

    date_from: date
    date_to: date
    currency: str
    requested: int
    pending: int
    approved: int
    rejected: int
    cancelled: int
    approved_value: Decimal
    approval_rate: Decimal | None  # approved / (approved + rejected), percent; None if no reviews
    pending_now: int  # all pending requests, regardless of date
    per_day: list[DayPoint]
    by_location: list[GroupRow]
    by_product: list[GroupRow]
    top_projects: list[ProjectRow]
