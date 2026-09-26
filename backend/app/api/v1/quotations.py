"""Customer side: product picker, quotation requests, own quotations and their PDFs.

Every query is scoped to the signed-in customer; another user's quotation looks like 404.
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.deps import DB, CustomerUser
from app.core.rate_limit import limiter
from app.models import Product, Profile, Quotation, QuotationStatus, User
from app.schemas.quotation import (
    CatalogProductOut,
    QuotationIn,
    QuotationOut,
    QuotationSummaryOut,
)
from app.services import audit
from app.services.catalog import check_dimensions, get_pricing_settings
from app.services.pricing import to_mm
from app.services.quotation_views import customer_view, pdf_response, summary
from app.services.quotations import (
    NOT_AVAILABLE,
    build_snapshot,
    price_product,
    quotable_products_query,
)

router = APIRouter(tags=["quotations"])


async def _own_quotation(
    db: DB, user: User, quotation_id: uuid.UUID, *, lock: bool = False
) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == quotation_id, Quotation.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    q = await db.scalar(stmt)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quotation not found")
    return q


@router.get("/catalog/products")
async def list_catalog(user: CustomerUser, db: DB) -> list[CatalogProductOut]:
    return [
        CatalogProductOut.model_validate(p) for p in await db.scalars(quotable_products_query())
    ]


@router.post("/quotations", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_quotation(
    request: Request, body: QuotationIn, user: CustomerUser, db: DB
) -> QuotationOut:
    profile = await db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Complete your profile before requesting a quotation"
        )
    pending = await db.scalar(
        select(func.count())
        .select_from(Quotation)
        .where(Quotation.user_id == user.id, Quotation.status == QuotationStatus.PENDING)
    )
    if (pending or 0) >= get_settings().max_pending_quotations:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You have too many pending quotations. Cancel some or wait for them to be reviewed.",
        )

    product = await db.get(Product, body.product_id)
    if product is None:
        raise NOT_AVAILABLE
    width_mm, height_mm = to_mm(body.width, body.unit), to_mm(body.height, body.unit)
    check_dimensions(product, width_mm, height_mm)
    settings = await get_pricing_settings(db)
    breakdown = await price_product(
        db, product, settings, width_mm=width_mm, height_mm=height_mm, quantity=body.quantity
    )

    quotation = Quotation(
        user_id=user.id,
        product_id=product.id,
        status=QuotationStatus.PENDING,
        input_width=body.width,
        input_height=body.height,
        input_unit=body.unit,
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=body.quantity,
        total=breakdown.total,
        currency=breakdown.currency,
        customer_city=profile.city,
        customer_province=profile.province,
        snapshot=build_snapshot(
            user=user,
            profile=profile,
            product=product,
            width=body.width,
            height=body.height,
            unit=body.unit,
            breakdown=breakdown,
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
        details={"product": product.code, "total": str(breakdown.total)},
    )
    await db.commit()
    await db.refresh(quotation)
    return customer_view(quotation)


@router.get("/quotations")
async def list_own_quotations(user: CustomerUser, db: DB) -> list[QuotationSummaryOut]:
    rows = await db.scalars(
        select(Quotation).where(Quotation.user_id == user.id).order_by(Quotation.created_at.desc())
    )
    return [summary(q) for q in rows]


@router.get("/quotations/{quotation_id}")
async def get_own_quotation(quotation_id: uuid.UUID, user: CustomerUser, db: DB) -> QuotationOut:
    return customer_view(await _own_quotation(db, user, quotation_id))


@router.post("/quotations/{quotation_id}/cancel")
async def cancel_quotation(
    quotation_id: uuid.UUID, user: CustomerUser, db: DB, request: Request
) -> QuotationOut:
    q = await _own_quotation(db, user, quotation_id, lock=True)
    if q.status != QuotationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only pending quotations can be cancelled")
    q.status = QuotationStatus.CANCELLED
    audit.record(
        db,
        "quotation.cancelled",
        request=request,
        actor_id=user.id,
        entity="quotation",
        entity_id=q.id,
    )
    await db.commit()
    await db.refresh(q)
    return customer_view(q)


@router.get("/quotations/{quotation_id}/pdf")
async def own_quotation_pdf(quotation_id: uuid.UUID, user: CustomerUser, db: DB) -> Response:
    q = await _own_quotation(db, user, quotation_id)
    return pdf_response(q, await get_pricing_settings(db))
