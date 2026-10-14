"""Catalogue rules shared by admin routes (and later, customer quotations)."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Basis,
    LaborRate,
    Material,
    PriceUnit,
    PricingSettings,
    Product,
    ProductComponent,
    ProductOption,
)
from app.models.catalog import BASIS_UNIT
from app.services.pricing import ComponentInput

UNIT_WORDS = {PriceUnit.SQM: "per m²", PriceUnit.LM: "per metre", PriceUnit.PIECE: "per piece"}


def ensure_basis_matches(basis: Basis, unit: PriceUnit) -> None:
    expected = BASIS_UNIT[basis]
    if unit != expected:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Basis '{basis}' needs an item priced {UNIT_WORDS[expected]}, "
            f"but this item is priced {UNIT_WORDS[unit]}",
        )


async def get_or_404[T](db: AsyncSession, model: type[T], id_: uuid.UUID, what: str) -> T:
    obj = await db.get(model, id_)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")
    return obj


async def ensure_code_free(
    db: AsyncSession, model: type[Material | LaborRate | Product], code: str, what: str
) -> None:
    if await db.scalar(select(model.id).where(model.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{what} code {code} already exists")


async def get_pricing_settings(db: AsyncSession) -> PricingSettings:
    settings = await db.get(PricingSettings, 1)
    if settings is None:  # created by migration 0002; missing means the DB is broken
        raise RuntimeError("pricing_settings row is missing")
    return settings


async def load_components(
    db: AsyncSession, product_id: uuid.UUID
) -> list[tuple[ProductComponent, Material | LaborRate]]:
    """Template lines with their material or labour rate, in display order."""
    rows = (
        await db.execute(
            select(ProductComponent, Material, LaborRate)
            .outerjoin(Material, Material.id == ProductComponent.material_id)
            .outerjoin(LaborRate, LaborRate.id == ProductComponent.labor_rate_id)
            .where(ProductComponent.product_id == product_id)
            .order_by(ProductComponent.sort_order, ProductComponent.created_at)
            # Reload from the DB so callers see stored values (e.g. 3 -> 3.0000), not cached ones.
            .execution_options(populate_existing=True)
        )
    ).all()
    result: list[tuple[ProductComponent, Material | LaborRate]] = []
    for component, material, labor in rows:
        item = material if material is not None else labor
        assert item is not None  # guaranteed by ck_product_components_material_xor_labor
        result.append((component, item))
    return result


async def load_options(db: AsyncSession, product_id: uuid.UUID) -> list[ProductOption]:
    """A product's add-ons, in display order."""
    return list(
        await db.scalars(
            select(ProductOption)
            .where(ProductOption.product_id == product_id)
            .order_by(ProductOption.sort_order, ProductOption.name)
        )
    )


async def get_option(
    db: AsyncSession, product_id: uuid.UUID, option_id: uuid.UUID
) -> ProductOption:
    """The add-on, only if it belongs to this product (otherwise 404)."""
    option = await db.get(ProductOption, option_id)
    if option is None or option.product_id != product_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Add-on not found")
    return option


def to_component_input(
    component: ProductComponent,
    item: Material | LaborRate,
    option_name: str = "",
    *,
    width_reduction_mm: int = 0,
    height_reduction_mm: int = 0,
) -> ComponentInput:
    is_material = isinstance(item, Material)
    return ComponentInput(
        kind="material" if is_material else "labor",
        code=item.code,
        name=item.name,
        label=component.label,
        basis=component.basis,
        unit=item.unit,
        unit_price=item.unit_price if isinstance(item, Material) else item.rate,
        factor=component.factor,
        waste_percent=component.waste_percent,
        option=option_name,
        width_reduction_mm=width_reduction_mm,
        height_reduction_mm=height_reduction_mm,
    )


def check_dimensions(product: Product, width_mm: int, height_mm: int) -> None:
    problems = []
    if not product.min_width_mm <= width_mm <= product.max_width_mm:
        problems.append(
            f"width must be {product.min_width_mm}-{product.max_width_mm} mm (got {width_mm} mm)"
        )
    if not product.min_height_mm <= height_mm <= product.max_height_mm:
        problems.append(
            f"height must be {product.min_height_mm}-{product.max_height_mm} mm "
            f"(got {height_mm} mm)"
        )
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "; ".join(problems))
