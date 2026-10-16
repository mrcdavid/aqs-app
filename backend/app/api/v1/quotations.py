"""Customer side: product picker, quotation requests, own quotations and their PDFs.

Every query is scoped to the signed-in customer; another user's quotation looks like 404.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser, CustomerUser
from app.core.rate_limit import limiter
from app.models import Profile, Quotation, QuotationStatus, User
from app.schemas.quotation import (
    CatalogChoiceGroupOut,
    CatalogOptionOut,
    CatalogProductOut,
    QuotationIn,
    QuotationOut,
    QuotationSummaryOut,
)
from app.services import audit
from app.services.catalog import get_pricing_settings
from app.services.quotation_views import customer_view, pdf_response, summary
from app.services.quotations import (
    catalog_offers,
    customer_details,
    not_deleted,
    price_items,
    quotable_products_query,
    quotation_snapshot,
)

router = APIRouter(tags=["quotations"])


async def _own_quotation(
    db: DB, user: User, quotation_id: uuid.UUID, *, lock: bool = False
) -> Quotation:
    stmt = select(Quotation).where(
        Quotation.id == quotation_id, Quotation.user_id == user.id, not_deleted()
    )
    if lock:
        stmt = stmt.with_for_update()
    q = await db.scalar(stmt)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quotation not found")
    return q


@router.get("/catalog/products")
async def list_catalog(user: CurrentUser, db: DB) -> list[CatalogProductOut]:
    """Quotable products with their available add-ons, for customers and for staff."""
    products = list(await db.scalars(quotable_products_query()))
    offers = await catalog_offers(db, products)
    result = []
    for p in products:
        offer = offers[p.id]
        if not offer.complete:  # e.g. every glass choice uses an archived material
            continue
        groups = [
            CatalogChoiceGroupOut(
                id=g.id,
                name=g.name,
                choices=[CatalogOptionOut.model_validate(c) for c in choices],
            )
            for g, choices in offer.groups
        ]
        add_ons = [CatalogOptionOut.model_validate(o) for o in offer.add_ons]
        result.append(
            CatalogProductOut.model_validate(p).model_copy(
                update={"choice_groups": groups, "options": add_ons}
            )
        )
    return result


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
        .where(
            Quotation.user_id == user.id,
            Quotation.status == QuotationStatus.PENDING,
            not_deleted(),
        )
    )
    if (pending or 0) >= get_settings().max_pending_quotations:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You have too many pending quotations. Cancel some or wait for them to be reviewed.",
        )

    settings = await get_pricing_settings(db)
    items = await price_items(db, settings, body.items)
    total = sum((i.amount for i in items), Decimal(0))
    quotation = Quotation(
        user_id=user.id,
        created_by=user.id,
        status=QuotationStatus.PENDING,
        total=total,
        currency=settings.currency,
        customer_city=profile.city,
        customer_province=profile.province,
        snapshot=quotation_snapshot(customer_details(user, profile)),
        items=items,
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
        details={"products": [i.product_name for i in items], "total": str(total)},
    )
    await db.commit()
    await db.refresh(quotation)
    return customer_view(quotation)


@router.get("/quotations")
async def list_own_quotations(user: CustomerUser, db: DB) -> list[QuotationSummaryOut]:
    rows = await db.scalars(
        select(Quotation)
        .where(Quotation.user_id == user.id, not_deleted())
        .order_by(Quotation.created_at.desc())
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
        details={"by": "customer"},
    )
    await db.commit()
    await db.refresh(q)
    return customer_view(q)


@router.get("/quotations/{quotation_id}/pdf")
async def own_quotation_pdf(quotation_id: uuid.UUID, user: CustomerUser, db: DB) -> Response:
    q = await _own_quotation(db, user, quotation_id)
    return pdf_response(q, await get_pricing_settings(db))
