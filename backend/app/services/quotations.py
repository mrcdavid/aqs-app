"""Quotation rules: what can be quoted, price snapshots, quote numbers, PDF files."""

import logging
import os
import uuid
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
from app.services.catalog import load_components, to_component_input
from app.services.pricing import PriceBreakdown, compute_price

logger = logging.getLogger("aqs.quotations")

# Philippine time (no daylight saving), used for quote dates and numbering.
PHT = timezone(timedelta(hours=8), "PHT")
SNAPSHOT_VERSION = 1


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


# ---------- which products customers can quote ----------


def _inactive_item_exists():  # noqa: ANN202 - SQLAlchemy expression
    """True when a product's template uses an archived material or labour rate."""
    return exists().where(
        ProductComponent.product_id == Product.id,
        (
            ProductComponent.material_id.in_(
                select(Material.id).where(Material.is_active.is_(False))
            )
            | ProductComponent.labor_rate_id.in_(
                select(LaborRate.id).where(LaborRate.is_active.is_(False))
            )
        ),
    )


def quotable_products_query():  # noqa: ANN201 - SQLAlchemy Select
    """Active products with a template whose items are all active."""
    return (
        select(Product)
        .where(
            Product.is_active.is_(True),
            exists().where(ProductComponent.product_id == Product.id),
            ~_inactive_item_exists(),
        )
        .order_by(Product.category, Product.name)
    )


NOT_AVAILABLE = HTTPException(status.HTTP_404_NOT_FOUND, "This product is not available")


async def price_product(
    db: AsyncSession,
    product: Product,
    settings: PricingSettings,
    *,
    width_mm: int,
    height_mm: int,
    quantity: int,
) -> PriceBreakdown:
    """Price a product for a customer. Refuses archived products or templates."""
    if not product.is_active:
        raise NOT_AVAILABLE
    components = await load_components(db, product.id)
    if not components or any(not item.is_active for _, item in components):
        raise NOT_AVAILABLE
    return compute_price(
        [to_component_input(c, item) for c, item in components],
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=quantity,
        markup_percent=settings.markup_percent,
        vat_percent=settings.vat_percent,
        currency=settings.currency,
    )


# ---------- snapshot ----------


def build_snapshot(
    *,
    user: User,
    profile: Profile,
    product: Product,
    width: Decimal,
    height: Decimal,
    unit: str,
    breakdown: PriceBreakdown,
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
            "customer": {
                "email": user.email,
                "full_name": profile.full_name,
                "contact_number": profile.contact_number,
                "address_line": profile.address_line,
                "city": profile.city,
                "province": profile.province,
            },
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
