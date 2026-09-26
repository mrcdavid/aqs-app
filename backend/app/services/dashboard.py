"""Dashboard figures, computed in SQL. Dates are Philippine dates (Asia/Manila)."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Quotation, QuotationStatus
from app.schemas.dashboard import DashboardOut, DayPoint, GroupRow, ProjectRow
from app.services.quotations import PHT

TZ = "Asia/Manila"
TOP_N = 10

APPROVED = Quotation.status == QuotationStatus.APPROVED
approved_count = func.count().filter(APPROVED)
approved_value = func.coalesce(func.sum(Quotation.total).filter(APPROVED), 0)


def _group_rows(rows: list[Any]) -> list[GroupRow]:
    return [
        GroupRow(
            label=r.label,
            requested=r.requested,
            approved=r.approved,
            approved_value=r.approved_value,
        )
        for r in rows
    ]


async def build_dashboard(
    db: AsyncSession, date_from: date, date_to: date, currency: str
) -> DashboardOut:
    start = datetime.combine(date_from, time.min, PHT)
    end = datetime.combine(date_to + timedelta(days=1), time.min, PHT)
    in_range = (Quotation.created_at >= start) & (Quotation.created_at < end)

    # Status counts and approved value
    counts = (
        await db.execute(
            select(Quotation.status, func.count(), func.coalesce(func.sum(Quotation.total), 0))
            .where(in_range)
            .group_by(Quotation.status)
        )
    ).all()
    by_status = {status: (n, value) for status, n, value in counts}
    n = {s: by_status.get(s, (0, Decimal(0)))[0] for s in QuotationStatus}
    value = by_status.get(QuotationStatus.APPROVED, (0, Decimal(0)))[1]
    reviewed = n[QuotationStatus.APPROVED] + n[QuotationStatus.REJECTED]
    rate = (
        (Decimal(n[QuotationStatus.APPROVED]) * 100 / reviewed).quantize(Decimal("0.1"))
        if reviewed
        else None
    )
    pending_now = await db.scalar(
        select(func.count())
        .select_from(Quotation)
        .where(Quotation.status == QuotationStatus.PENDING)
    )

    # Per day, with empty days filled in so the chart has no gaps
    local_day = cast(func.timezone(TZ, Quotation.created_at), Date).label("day")
    day_rows = (
        await db.execute(
            select(local_day, func.count(), approved_count, approved_value)
            .where(in_range)
            .group_by(local_day)
        )
    ).all()
    by_day = {d: (req, appr, val) for d, req, appr, val in day_rows}
    per_day = []
    d = date_from
    while d <= date_to:
        req, appr, val = by_day.get(d, (0, 0, Decimal(0)))
        per_day.append(DayPoint(day=d, requested=req, approved=appr, approved_value=val))
        d += timedelta(days=1)

    # By location (province) and by product
    province = Quotation.customer_province.label("label")
    by_location = (
        await db.execute(
            select(
                province,
                func.count().label("requested"),
                approved_count.label("approved"),
                approved_value.label("approved_value"),
            )
            .where(in_range)
            .group_by(province)
            .order_by(func.count().desc(), province)
            .limit(TOP_N)
        )
    ).all()
    product_name = Quotation.snapshot["product"]["name"].astext.label("label")
    by_product = (
        await db.execute(
            select(
                product_name,
                func.count().label("requested"),
                approved_count.label("approved"),
                approved_value.label("approved_value"),
            )
            .where(in_range)
            .group_by(product_name)
            .order_by(func.count().desc(), product_name)
            .limit(TOP_N)
        )
    ).all()

    # Largest approved projects
    top = await db.scalars(
        select(Quotation).where(in_range, APPROVED).order_by(Quotation.total.desc()).limit(TOP_N)
    )
    top_projects = [
        ProjectRow(
            id=str(q.id),
            number=q.number,
            customer_name=q.snapshot["customer"]["full_name"],
            product_name=q.snapshot["product"]["name"],
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
        requested=sum(n.values()),
        pending=n[QuotationStatus.PENDING],
        approved=n[QuotationStatus.APPROVED],
        rejected=n[QuotationStatus.REJECTED],
        cancelled=n[QuotationStatus.CANCELLED],
        approved_value=value,
        approval_rate=rate,
        pending_now=pending_now or 0,
        per_day=per_day,
        by_location=_group_rows(by_location),
        by_product=_group_rows(by_product),
        top_projects=top_projects,
    )
