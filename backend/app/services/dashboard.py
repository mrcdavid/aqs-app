"""Dashboard figures, computed in SQL. Dates are Philippine dates (Asia/Manila).

Everything counts approved quotations only (requested within the date range), except the
approval rate, which also needs the rejected count, and the number still waiting for review.
Deleted quotations never count.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Quotation, QuotationItem, QuotationStatus
from app.schemas.dashboard import DashboardOut, DayPoint, GroupRow, ProjectRow
from app.services.quotations import PHT, not_deleted

TZ = "Asia/Manila"
TOP_N = 10

APPROVED = Quotation.status == QuotationStatus.APPROVED


def _group_rows(rows: list[Any]) -> list[GroupRow]:
    return [
        GroupRow(label=r.label, approved=r.approved, approved_value=r.approved_value) for r in rows
    ]


async def build_dashboard(
    db: AsyncSession, date_from: date, date_to: date, currency: str
) -> DashboardOut:
    start = datetime.combine(date_from, time.min, PHT)
    end = datetime.combine(date_to + timedelta(days=1), time.min, PHT)
    in_range = (Quotation.created_at >= start) & (Quotation.created_at < end) & not_deleted()
    approved_in_range = in_range & APPROVED

    # Approved count and value; rejected count only for the approval rate.
    approved, value = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Quotation.total), 0)).where(
                approved_in_range
            )
        )
    ).one()
    rejected = await db.scalar(
        select(func.count())
        .select_from(Quotation)
        .where(in_range, Quotation.status == QuotationStatus.REJECTED)
    )
    rejected = rejected or 0
    reviewed = approved + rejected
    rate = (Decimal(approved) * 100 / reviewed).quantize(Decimal("0.1")) if reviewed else None
    average = (Decimal(value) / approved).quantize(Decimal("0.01")) if approved else None
    pending_now = await db.scalar(
        select(func.count())
        .select_from(Quotation)
        .where(Quotation.status == QuotationStatus.PENDING, not_deleted())
    )

    # Per day, with empty days filled in so the chart has no gaps
    local_day = cast(func.timezone(TZ, Quotation.created_at), Date).label("day")
    day_rows = (
        await db.execute(
            select(local_day, func.count(), func.sum(Quotation.total))
            .where(approved_in_range)
            .group_by(local_day)
        )
    ).all()
    by_day = {d: (n, val) for d, n, val in day_rows}
    per_day = []
    d = date_from
    while d <= date_to:
        n, val = by_day.get(d, (0, Decimal(0)))
        per_day.append(DayPoint(day=d, approved=n, approved_value=val))
        d += timedelta(days=1)

    # By location (province), largest approved value first
    province = Quotation.customer_province.label("label")
    location_value = func.sum(Quotation.total)
    by_location = (
        await db.execute(
            select(
                province,
                func.count().label("approved"),
                location_value.label("approved_value"),
            )
            .where(approved_in_range)
            .group_by(province)
            .order_by(location_value.desc(), province)
            .limit(TOP_N)
        )
    ).all()

    # By product: a quotation can hold several products; count it once per product and value
    # each product by its own item amounts.
    product_name = QuotationItem.product_name.label("label")
    product_value = func.sum(QuotationItem.amount)
    by_product = (
        await db.execute(
            select(
                product_name,
                func.count(func.distinct(Quotation.id)).label("approved"),
                product_value.label("approved_value"),
            )
            .join(Quotation, Quotation.id == QuotationItem.quotation_id)
            .where(approved_in_range)
            .group_by(product_name)
            .order_by(product_value.desc(), product_name)
            .limit(TOP_N)
        )
    ).all()

    # Largest approved projects
    top = await db.scalars(
        select(Quotation).where(approved_in_range).order_by(Quotation.total.desc()).limit(TOP_N)
    )
    top_projects = [
        ProjectRow(
            id=str(q.id),
            number=q.number,
            customer_name=q.snapshot["customer"]["full_name"],
            product_name=q.items[0].product_name
            + (f" + {len(q.items) - 1} more" if len(q.items) > 1 else ""),
            city=q.customer_city,
            total=q.total,
            created_at=q.created_at.isoformat(),
        )
        for q in top
    ]

    return DashboardOut(
        date_from=date_from,
        date_to=date_to,
        currency=currency,
        approved=approved,
        approved_value=value,
        average_value=average,
        rejected=rejected,
        approval_rate=rate,
        pending_now=pending_now or 0,
        per_day=per_day,
        by_location=_group_rows(by_location),
        by_product=_group_rows(by_product),
        top_projects=top_projects,
    )
