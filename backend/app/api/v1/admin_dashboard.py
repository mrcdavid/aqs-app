"""Dashboard for staff: quotations per day, by location, by product, largest projects."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import DB, StaffUser
from app.schemas.dashboard import DashboardOut
from app.services.catalog import get_pricing_settings
from app.services.dashboard import build_dashboard
from app.services.quotations import today_pht

router = APIRouter(prefix="/admin/dashboard", tags=["admin: dashboard"])

MAX_DAYS = 366


@router.get("")
async def dashboard(
    user: StaffUser,
    db: DB,
    date_from: Annotated[date | None, Query(description="Philippine date, inclusive")] = None,
    date_to: Annotated[date | None, Query(description="Philippine date, inclusive")] = None,
) -> DashboardOut:
    date_to = date_to or today_pht()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Start date is after end date")
    if (date_to - date_from).days >= MAX_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Choose a range of at most {MAX_DAYS} days"
        )
    settings = await get_pricing_settings(db)
    return await build_dashboard(db, date_from, date_to, settings.currency)
