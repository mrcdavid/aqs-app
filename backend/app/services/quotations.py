"""Quotation rules: what can be quoted, price snapshots, quote numbers, PDF files."""

import logging
import os
import uuid
from collections import defaultdict
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
    ProductOption,
    Profile,
    QuoteCounter,
    User,
)
from app.services.catalog import load_components, load_options, to_component_input
from app.services.pricing import PriceBreakdown, compute_price, money

logger = logging.getLogger("aqs.quotations")

# Philippine time (no daylight saving), used for quote dates and numbering.
PHT = timezone(timedelta(hours=8), "PHT")
# 2: pricing has rounding_step/rounding/rounded_total; customer email may be empty (walk-in).
# 3: chosen add-ons in `options`; pricing lines carry `option` ("" = always included).
SNAPSHOT_VERSION = 3
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


async def available_options(
    db: AsyncSession, product_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[ProductOption]]:
    """Add-ons that can be chosen: at least one line, and no archived items. Per product."""
    if not product_ids:
        return {}
    own_line = ProductComponent.option_id == ProductOption.id
    rows = await db.scalars(
        select(ProductOption)
        .where(
            ProductOption.product_id.in_(product_ids),
            exists().where(own_line),
            ~exists().where(own_line, _uses_archived_item()),
        )
        .order_by(ProductOption.sort_order, ProductOption.name)
    )
    result: dict[uuid.UUID, list[ProductOption]] = defaultdict(list)
    for option in rows:
        result[option.product_id].append(option)
    return result


NOT_AVAILABLE = HTTPException(status.HTTP_404_NOT_FOUND, "This product is not available")
OPTION_NOT_AVAILABLE = HTTPException(
    status.HTTP_422_UNPROCESSABLE_CONTENT, "This add-on is not available"
)


async def price_product(
    db: AsyncSession,
    product: Product,
    settings: PricingSettings,
    *,
    width_mm: int,
    height_mm: int,
    quantity: int,
    option_ids: Sequence[uuid.UUID] = (),
) -> tuple[PriceBreakdown, list[ProductOption]]:
    """Price a product plus the chosen add-ons. Refuses archived products, templates or add-ons.

    Returns the breakdown and the chosen add-ons (in display order).
    """
    if not product.is_active:
        raise NOT_AVAILABLE
    components = await load_components(db, product.id)
    base = [(c, item) for c, item in components if c.option_id is None]
    if not base or any(not item.is_active for _, item in base):
        raise NOT_AVAILABLE

    options = {o.id: o for o in await load_options(db, product.id)}
    chosen: list[ProductOption] = []
    for option_id in option_ids:
        lines = [item for c, item in components if c.option_id == option_id]
        if option_id not in options or not lines or any(not item.is_active for item in lines):
            raise OPTION_NOT_AVAILABLE
        chosen.append(options[option_id])
    chosen.sort(key=lambda o: (o.sort_order, o.name))
    names = {o.id: o.name for o in chosen}

    breakdown = compute_price(
        [
            to_component_input(c, item, names[c.option_id] if c.option_id else "")
            for c, item in components
            if c.option_id is None or c.option_id in names
        ],
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=quantity,
        markup_percent=settings.markup_percent,
        vat_percent=settings.vat_percent,
        currency=settings.currency,
        rounding_step=settings.rounding_step,
    )
    return breakdown, chosen


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
    options: Sequence[ProductOption] = (),
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
            "options": [{"name": o.name, "description": o.description} for o in options],
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
