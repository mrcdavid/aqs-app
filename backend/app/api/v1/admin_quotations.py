"""Admin side: review quotation requests, approve (assigns number + final PDF) or reject."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select

from app.core.deps import DB, StaffUser
from app.models import Quotation, QuotationStatus, User
from app.schemas.quotation import AdminQuotationOut, AdminQuotationSummaryOut, RejectIn, ReviewIn
from app.services import audit
from app.services.catalog import get_pricing_settings
from app.services.quotation_views import admin_summary, admin_view, pdf_response, store_final_pdf
from app.services.quotations import business_snapshot, next_quote_number, today_pht
from app.services.sessions import utcnow

router = APIRouter(prefix="/admin/quotations", tags=["admin: quotations"])

LIST_LIMIT = 500


async def _get(db: DB, quotation_id: uuid.UUID, *, lock: bool = False) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == quotation_id)
    if lock:
        stmt = stmt.with_for_update()
    q = await db.scalar(stmt)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quotation not found")
    return q


async def _view(db: DB, q: Quotation) -> AdminQuotationOut:
    reviewer = (
        await db.scalar(select(User.email).where(User.id == q.reviewed_by))
        if q.reviewed_by
        else None
    )
    return admin_view(q, reviewer)


def _ensure_pending(q: Quotation) -> None:
    if q.status != QuotationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This quotation is already {q.status}")


@router.get("")
async def list_quotations(
    user: StaffUser,
    db: DB,
    status_filter: Annotated[QuotationStatus | None, Query(alias="status")] = None,
) -> list[AdminQuotationSummaryOut]:
    stmt = select(Quotation).order_by(Quotation.created_at.desc()).limit(LIST_LIMIT)
    if status_filter is not None:
        stmt = stmt.where(Quotation.status == status_filter)
    return [admin_summary(q) for q in await db.scalars(stmt)]


@router.get("/{quotation_id}")
async def get_quotation(quotation_id: uuid.UUID, user: StaffUser, db: DB) -> AdminQuotationOut:
    return await _view(db, await _get(db, quotation_id))


@router.post("/{quotation_id}/approve")
async def approve_quotation(
    quotation_id: uuid.UUID, body: ReviewIn, user: StaffUser, db: DB, request: Request
) -> AdminQuotationOut:
    q = await _get(db, quotation_id, lock=True)  # row lock: two admins can't both approve
    _ensure_pending(q)
    settings = await get_pricing_settings(db)
    today = today_pht()

    q.number = await next_quote_number(db, today.year)
    q.status = QuotationStatus.APPROVED
    q.reviewed_by = user.id
    q.reviewed_at = utcnow()
    q.review_note = body.note or None
    q.valid_until = today + timedelta(days=settings.quote_validity_days)
    q.pdf_file = f"{q.number}.pdf"
    # Freeze the business details printed on the final PDF (new dict so JSONB change is saved).
    q.snapshot = {**q.snapshot, "business": business_snapshot(settings)}
    audit.record(
        db,
        "quotation.approved",
        request=request,
        actor_id=user.id,
        entity="quotation",
        entity_id=q.id,
        details={"number": q.number, "total": str(q.total)},
    )
    await db.commit()
    await db.refresh(q)

    store_final_pdf(q)
    return await _view(db, q)


@router.post("/{quotation_id}/reject")
async def reject_quotation(
    quotation_id: uuid.UUID, body: RejectIn, user: StaffUser, db: DB, request: Request
) -> AdminQuotationOut:
    q = await _get(db, quotation_id, lock=True)
    _ensure_pending(q)
    q.status = QuotationStatus.REJECTED
    q.reviewed_by = user.id
    q.reviewed_at = utcnow()
    q.review_note = body.note
    audit.record(
        db,
        "quotation.rejected",
        request=request,
        actor_id=user.id,
        entity="quotation",
        entity_id=q.id,
    )
    await db.commit()
    await db.refresh(q)
    return await _view(db, q)


@router.get("/{quotation_id}/pdf")
async def quotation_pdf(quotation_id: uuid.UUID, user: StaffUser, db: DB) -> Response:
    q = await _get(db, quotation_id)
    return pdf_response(q, await get_pricing_settings(db))
