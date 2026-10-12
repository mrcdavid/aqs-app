"""Admin side: quote walk-in clients, review requests, approve (number + final PDF) or reject."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select

from app.core.deps import DB, StaffUser
from app.core.rate_limit import limiter
from app.models import Product, Quotation, QuotationStatus, User
from app.schemas.quotation import (
    AdminQuotationOut,
    AdminQuotationSummaryOut,
    RejectIn,
    ReviewIn,
    StaffQuotationIn,
)
from app.services import audit
from app.services.catalog import check_dimensions, get_pricing_settings
from app.services.pricing import to_mm
from app.services.quotation_views import admin_summary, admin_view, pdf_response, store_final_pdf
from app.services.quotations import (
    NOT_AVAILABLE,
    build_snapshot,
    business_snapshot,
    next_quote_number,
    price_product,
    today_pht,
)
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


async def _email(db: DB, user_id: uuid.UUID | None) -> str | None:
    return await db.scalar(select(User.email).where(User.id == user_id)) if user_id else None


async def _view(db: DB, q: Quotation) -> AdminQuotationOut:
    return admin_view(
        q,
        created_by_email=await _email(db, q.created_by),
        reviewed_by_email=await _email(db, q.reviewed_by),
    )


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


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_quotation_for_client(
    request: Request, body: StaffQuotationIn, user: StaffUser, db: DB
) -> AdminQuotationOut:
    """Quote a walk-in client (no account). Priced like a customer request; starts pending."""
    product = await db.get(Product, body.product_id)
    if product is None:
        raise NOT_AVAILABLE
    width_mm, height_mm = to_mm(body.width, body.unit), to_mm(body.height, body.unit)
    check_dimensions(product, width_mm, height_mm)
    settings = await get_pricing_settings(db)
    breakdown, options = await price_product(
        db,
        product,
        settings,
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=body.quantity,
        option_ids=body.option_ids,
    )

    client = body.client
    quotation = Quotation(
        user_id=None,
        created_by=user.id,
        product_id=product.id,
        status=QuotationStatus.PENDING,
        input_width=body.width,
        input_height=body.height,
        input_unit=body.unit,
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=body.quantity,
        total=breakdown.rounded_total,
        currency=breakdown.currency,
        customer_city=client.city,
        customer_province=client.province,
        snapshot=build_snapshot(
            customer={**client.model_dump(), "email": client.email or ""},
            product=product,
            width=body.width,
            height=body.height,
            unit=body.unit,
            breakdown=breakdown,
            options=options,
        ),
    )
    db.add(quotation)
    await db.flush()
    audit.record(
        db,
        "quotation.created",
        request=request,
        actor_id=user.id,
        entity="quotation",
        entity_id=quotation.id,
        details={
            "product": product.code,
            "options": [o.name for o in options],
            "total": str(breakdown.rounded_total),
            "walk_in_client": client.full_name,
        },
    )
    await db.commit()
    await db.refresh(quotation)
    return await _view(db, quotation)


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

    details: dict[str, str] = {}
    if body.final_total is not None and body.final_total != q.total:
        details["adjusted_from"] = str(q.total)
        q.total = body.final_total
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
        details={"number": q.number, "total": str(q.total), **details},
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
