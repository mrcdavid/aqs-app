"""Quotation rules: what can be quoted, price snapshots, quote numbers, PDF files."""

import logging
import os
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    LaborRate,
    Material,
    PricingSettings,
    Product,
    ProductComponent,
    Profile,
    QuoteCounter,
    User,
)
from app.services.catalog import load_components, load_options
from app.services.options import (
    OPTION_NOT_AVAILABLE,
    Offer,
    Picked,
    load_groups,
    offer,
    pick,
    priced_lines,
)
from app.services.pricing import PriceBreakdown, compute_price, money

logger = logging.getLogger("aqs.quotations")

# Philippine time (no daylight saving), used for quote dates and numbering.
PHT = timezone(timedelta(hours=8), "PHT")
# 2: pricing has rounding_step/rounding/rounded_total; customer email may be empty (walk-in).
# 3: chosen add-ons in `options`; pricing lines carry `option` ("" = always included).
# 4: chosen group choices in `choices`; pricing lines carry the size they were measured at.
SNAPSHOT_VERSION = 4
DOWNPAYMENT_PERCENT = Decimal(50)


def today_pht() -> date:
    return datetime.now(UTC).astimezone(PHT).date()


def to_json(value: Any) -> Any:
    """Snapshot-safe JSON: Decimal -> str (never float), Enum -> value, recursively."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    return value


# ---------- which products (and add-ons) can be quoted ----------


def _uses_archived_item():  # noqa: ANN202 - SQLAlchemy expression
    """True for a template line whose material or labour rate is archived."""
    return ProductComponent.material_id.in_(
        select(Material.id).where(Material.is_active.is_(False))
    ) | ProductComponent.labor_rate_id.in_(
        select(LaborRate.id).where(LaborRate.is_active.is_(False))
    )


def quotable_products_query():  # noqa: ANN201 - SQLAlchemy Select
    """Active products whose always-included lines exist and are all active.

    Add-on lines don't count: an archived add-on item only hides that add-on.
    """
    base_line = (ProductComponent.product_id == Product.id) & ProductComponent.option_id.is_(None)
    return (
        select(Product)
        .where(
            Product.is_active.is_(True),
            exists().where(base_line),
            ~exists().where(base_line, _uses_archived_item()),
        )
        .order_by(Product.category, Product.name)
    )


async def catalog_offers(db: AsyncSession, products: Sequence[Product]) -> dict[uuid.UUID, Offer]:
    """What can be chosen for each product. Products with an incomplete offer can't be quoted."""
    result = {}
    for product in products:
        result[product.id] = offer(
            await load_components(db, product.id),
            await load_groups(db, product.id),
            await load_options(db, product.id),
        )
    return result


NOT_AVAILABLE = HTTPException(status.HTTP_404_NOT_FOUND, "This product is not available")


async def price_product(
    db: AsyncSession,
    product: Product,
    settings: PricingSettings,
    *,
    width_mm: int,
    height_mm: int,
    quantity: int,
    option_ids: Sequence[uuid.UUID] = (),
) -> tuple[PriceBreakdown, Picked]:
    """Price a product with the chosen options. Refuses archived products, templates or options.

    `option_ids` holds the chosen add-ons and exactly one choice per group.
    """
    if not product.is_active:
        raise NOT_AVAILABLE
    components = await load_components(db, product.id)
    base = [(c, item) for c, item in components if c.option_id is None]
    if not base or any(not item.is_active for _, item in base):
        raise NOT_AVAILABLE

    groups = await load_groups(db, product.id)
    options = await load_options(db, product.id)
    offered = offer(components, groups, options)
    if not offered.complete:
        raise NOT_AVAILABLE
    usable = {o.id for o in offered.add_ons} | {o.id for _, cs in offered.groups for o in cs}
    if any(option_id not in usable for option_id in option_ids):
        raise OPTION_NOT_AVAILABLE
    picked = pick(groups, options, option_ids)

    try:
        breakdown = compute_price(
            priced_lines(components, picked),
            width_mm=width_mm,
            height_mm=height_mm,
            quantity=quantity,
            markup_percent=settings.markup_percent,
            vat_percent=settings.vat_percent,
            currency=settings.currency,
            rounding_step=settings.rounding_step,
        )
    except ValueError as exc:  # e.g. the opening is too small for the open back
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return breakdown, picked


def payment_split(total: Decimal) -> tuple[Decimal, Decimal]:
    """50% downpayment, 50% on completion and installation. The two always add up to total."""
    downpayment = money(total * DOWNPAYMENT_PERCENT / 100)
    return downpayment, total - downpayment


# ---------- snapshot ----------


def customer_details(user: User, profile: Profile) -> dict[str, str]:
    """A signed-in customer's details, as printed on the quotation."""
    return {
        "email": user.email,
        "full_name": profile.full_name,
        "contact_number": profile.contact_number,
        "address_line": profile.address_line,
        "city": profile.city,
        "province": profile.province,
    }


def build_snapshot(
    *,
    customer: dict[str, str],
    product: Product,
    width: Decimal,
    height: Decimal,
    unit: str,
    breakdown: PriceBreakdown,
    picked: Picked | None = None,
) -> dict[str, Any]:
    return to_json(
        {
            "version": SNAPSHOT_VERSION,
            "product": {
                "code": product.code,
                "name": product.name,
                "category": product.category,
                "description": product.description,
            },
            "customer": customer,
            **(picked or Picked(choices=[], add_ons=[])).snapshot(),
            "input": {"width": width, "height": height, "unit": unit},
            "pricing": breakdown.as_dict(),
        }
    )


def business_snapshot(settings: PricingSettings) -> dict[str, Any]:
    return {
        "name": settings.business_name,
        "address": settings.business_address,
        "contact": settings.business_contact,
        "terms": settings.quote_terms,
        "owner_name": settings.owner_name,
    }


# ---------- numbering ----------


async def next_quote_number(db: AsyncSession, year: int) -> str:
    """AQS-<year>-<6 digits>. The upsert takes a row lock, so concurrent approvals never clash."""
    stmt = (
        insert(QuoteCounter)
        .values(year=year, last_number=1)
        .on_conflict_do_update(
            index_elements=[QuoteCounter.year],
            set_={"last_number": QuoteCounter.last_number + 1},
        )
        .returning(QuoteCounter.last_number)
    )
    n = (await db.execute(stmt)).scalar_one()
    return f"AQS-{year}-{n:06d}"


# ---------- stored PDFs ----------


def pdf_dir() -> Path:
    path = get_settings().quote_storage_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_pdf(file_name: str, data: bytes) -> None:
    """Write atomically so a half-written file is never served."""
    target = pdf_dir() / file_name
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, target)


def read_pdf(file_name: str) -> bytes | None:
    path = pdf_dir() / file_name
    return path.read_bytes() if path.is_file() else None
