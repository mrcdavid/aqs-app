"""Admin catalogue: materials, labour rates, products + templates, pricing settings.

Staff only (admin, super_admin). Nothing here is hard-deleted except template lines;
materials, labour rates and products are archived with is_active=false.
Every change is audited with before/after values.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core.deps import DB, StaffUser
from app.models import LaborRate, Material, Product, ProductComponent
from app.schemas.catalog import (
    ComponentIn,
    ComponentOut,
    ComponentUpdate,
    LaborRateIn,
    LaborRateOut,
    LaborRateUpdate,
    MaterialIn,
    MaterialOut,
    MaterialUpdate,
    PricePreviewIn,
    PricePreviewOut,
    PricingSettingsIn,
    PricingSettingsOut,
    ProductDetailOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
)
from app.services import audit
from app.services.catalog import (
    check_dimensions,
    ensure_basis_matches,
    ensure_code_free,
    get_or_404,
    get_pricing_settings,
    load_components,
    to_component_input,
)
from app.services.pricing import compute_price, to_mm

router = APIRouter(prefix="/admin", tags=["admin: catalogue"])

MATERIAL_FIELDS = ["code", "name", "category", "unit", "unit_price", "is_active"]
LABOR_FIELDS = ["code", "name", "unit", "rate", "is_active"]
PRODUCT_FIELDS = [
    "code",
    "name",
    "category",
    "description",
    "min_width_mm",
    "max_width_mm",
    "min_height_mm",
    "max_height_mm",
    "is_active",
]
COMPONENT_FIELDS = [
    "material_id",
    "labor_rate_id",
    "basis",
    "factor",
    "waste_percent",
    "label",
    "sort_order",
]
SETTINGS_FIELDS = [
    "markup_percent",
    "vat_percent",
    "currency",
    "quote_validity_days",
    "business_name",
    "business_address",
    "business_contact",
    "quote_terms",
]


def _patch_values(body: Any) -> dict[str, Any]:
    """Fields the client actually sent; null means 'leave unchanged'."""
    return {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}


async def _item_in_use(db: DB, column: Any, item_id: uuid.UUID) -> bool:
    return (
        await db.scalar(select(ProductComponent.id).where(column == item_id).limit(1))
    ) is not None


# ---------- materials ----------


@router.get("/materials")
async def list_materials(user: StaffUser, db: DB) -> list[MaterialOut]:
    rows = await db.scalars(
        select(Material).order_by(Material.is_active.desc(), Material.category, Material.name)
    )
    return [MaterialOut.model_validate(m) for m in rows]


@router.post("/materials", status_code=status.HTTP_201_CREATED)
async def create_material(
    body: MaterialIn, user: StaffUser, db: DB, request: Request
) -> MaterialOut:
    await ensure_code_free(db, Material, body.code, "Material")
    material = Material(**body.model_dump())
    db.add(material)
    await db.flush()
    audit.record(
        db,
        "material.created",
        request=request,
        actor_id=user.id,
        entity="material",
        entity_id=material.id,
        details={"after": audit.snapshot(material, MATERIAL_FIELDS)},
    )
    await db.commit()
    await db.refresh(material)
    return MaterialOut.model_validate(material)


@router.patch("/materials/{material_id}")
async def update_material(
    material_id: uuid.UUID, body: MaterialUpdate, user: StaffUser, db: DB, request: Request
) -> MaterialOut:
    material = await get_or_404(db, Material, material_id, "Material")
    values = _patch_values(body)
    if "code" in values and values["code"] != material.code:
        await ensure_code_free(db, Material, values["code"], "Material")
    if "unit" in values and values["unit"] != material.unit:
        if await _item_in_use(db, ProductComponent.material_id, material.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This material is used in product templates; remove it there before changing "
                "its unit, or create a new material",
            )
    before = audit.snapshot(material, MATERIAL_FIELDS)
    for field, value in values.items():
        setattr(material, field, value)
    after = audit.snapshot(material, MATERIAL_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "material.updated",
            request=request,
            actor_id=user.id,
            entity="material",
            entity_id=material.id,
            details={"changes": diff},
        )
    await db.commit()
    await db.refresh(material)
    return MaterialOut.model_validate(material)


# ---------- labour rates ----------


@router.get("/labor-rates")
async def list_labor_rates(user: StaffUser, db: DB) -> list[LaborRateOut]:
    rows = await db.scalars(select(LaborRate).order_by(LaborRate.is_active.desc(), LaborRate.name))
    return [LaborRateOut.model_validate(r) for r in rows]


@router.post("/labor-rates", status_code=status.HTTP_201_CREATED)
async def create_labor_rate(
    body: LaborRateIn, user: StaffUser, db: DB, request: Request
) -> LaborRateOut:
    await ensure_code_free(db, LaborRate, body.code, "Labour rate")
    rate = LaborRate(**body.model_dump())
    db.add(rate)
    await db.flush()
    audit.record(
        db,
        "labor_rate.created",
        request=request,
        actor_id=user.id,
        entity="labor_rate",
        entity_id=rate.id,
        details={"after": audit.snapshot(rate, LABOR_FIELDS)},
    )
    await db.commit()
    await db.refresh(rate)
    return LaborRateOut.model_validate(rate)


@router.patch("/labor-rates/{rate_id}")
async def update_labor_rate(
    rate_id: uuid.UUID, body: LaborRateUpdate, user: StaffUser, db: DB, request: Request
) -> LaborRateOut:
    rate = await get_or_404(db, LaborRate, rate_id, "Labour rate")
    values = _patch_values(body)
    if "code" in values and values["code"] != rate.code:
        await ensure_code_free(db, LaborRate, values["code"], "Labour rate")
    if "unit" in values and values["unit"] != rate.unit:
        if await _item_in_use(db, ProductComponent.labor_rate_id, rate.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This labour rate is used in product templates; remove it there before "
                "changing its unit, or create a new labour rate",
            )
    before = audit.snapshot(rate, LABOR_FIELDS)
    for field, value in values.items():
        setattr(rate, field, value)
    after = audit.snapshot(rate, LABOR_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "labor_rate.updated",
            request=request,
            actor_id=user.id,
            entity="labor_rate",
            entity_id=rate.id,
            details={"changes": diff},
        )
    await db.commit()
    await db.refresh(rate)
    return LaborRateOut.model_validate(rate)


# ---------- products ----------


async def _product_detail(db: DB, product: Product) -> ProductDetailOut:
    components = []
    for component, item in await load_components(db, product.id):
        is_material = isinstance(item, Material)
        components.append(
            ComponentOut(
                id=component.id,
                kind="material" if is_material else "labor",
                material_id=component.material_id,
                labor_rate_id=component.labor_rate_id,
                item_code=item.code,
                item_name=item.name,
                item_unit=item.unit,
                item_price=item.unit_price if isinstance(item, Material) else item.rate,
                item_active=item.is_active,
                basis=component.basis,
                factor=component.factor,
                waste_percent=component.waste_percent,
                label=component.label,
                sort_order=component.sort_order,
            )
        )
    base = ProductOut.model_validate(product).model_dump()
    return ProductDetailOut(**base, components=components)


@router.get("/products")
async def list_products(user: StaffUser, db: DB) -> list[ProductOut]:
    rows = await db.scalars(
        select(Product).order_by(Product.is_active.desc(), Product.category, Product.name)
    )
    return [ProductOut.model_validate(p) for p in rows]


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductIn, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    await ensure_code_free(db, Product, body.code, "Product")
    product = Product(**body.model_dump())
    db.add(product)
    await db.flush()
    audit.record(
        db,
        "product.created",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={"after": audit.snapshot(product, PRODUCT_FIELDS)},
    )
    await db.commit()
    await db.refresh(product)
    return await _product_detail(db, product)


@router.get("/products/{product_id}")
async def get_product(product_id: uuid.UUID, user: StaffUser, db: DB) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    return await _product_detail(db, product)


@router.patch("/products/{product_id}")
async def update_product(
    product_id: uuid.UUID, body: ProductUpdate, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    values = _patch_values(body)
    if "code" in values and values["code"] != product.code:
        await ensure_code_free(db, Product, values["code"], "Product")
    before = audit.snapshot(product, PRODUCT_FIELDS)
    for field, value in values.items():
        setattr(product, field, value)
    if product.min_width_mm > product.max_width_mm or product.min_height_mm > product.max_height_mm:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Minimum size must not exceed maximum size"
        )
    after = audit.snapshot(product, PRODUCT_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "product.updated",
            request=request,
            actor_id=user.id,
            entity="product",
            entity_id=product.id,
            details={"changes": diff},
        )
    await db.commit()
    await db.refresh(product)
    return await _product_detail(db, product)


# ---------- product template (components) ----------


@router.post("/products/{product_id}/components", status_code=status.HTTP_201_CREATED)
async def add_component(
    product_id: uuid.UUID, body: ComponentIn, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    item: Material | LaborRate
    if body.material_id is not None:
        item = await get_or_404(db, Material, body.material_id, "Material")
    else:
        assert body.labor_rate_id is not None
        item = await get_or_404(db, LaborRate, body.labor_rate_id, "Labour rate")
    if not item.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{item.code} is archived")
    ensure_basis_matches(body.basis, item.unit)

    component = ProductComponent(product_id=product.id, **body.model_dump())
    db.add(component)
    await db.flush()
    audit.record(
        db,
        "product.component_added",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={
            "component_id": str(component.id),
            "item": item.code,
            "after": audit.snapshot(component, COMPONENT_FIELDS),
        },
    )
    await db.commit()
    return await _product_detail(db, product)


async def _get_component(
    db: DB, product_id: uuid.UUID, component_id: uuid.UUID
) -> ProductComponent:
    component = await db.get(ProductComponent, component_id)
    if component is None or component.product_id != product_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Component not found")
    return component


@router.patch("/products/{product_id}/components/{component_id}")
async def update_component(
    product_id: uuid.UUID,
    component_id: uuid.UUID,
    body: ComponentUpdate,
    user: StaffUser,
    db: DB,
    request: Request,
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    component = await _get_component(db, product_id, component_id)
    values = _patch_values(body)
    if "basis" in values:
        item = (
            await db.get(Material, component.material_id)
            if component.material_id
            else await db.get(LaborRate, component.labor_rate_id)
        )
        assert item is not None
        ensure_basis_matches(values["basis"], item.unit)
    before = audit.snapshot(component, COMPONENT_FIELDS)
    for field, value in values.items():
        setattr(component, field, value)
    after = audit.snapshot(component, COMPONENT_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "product.component_updated",
            request=request,
            actor_id=user.id,
            entity="product",
            entity_id=product.id,
            details={"component_id": str(component.id), "changes": diff},
        )
    await db.commit()
    return await _product_detail(db, product)


@router.delete("/products/{product_id}/components/{component_id}")
async def remove_component(
    product_id: uuid.UUID, component_id: uuid.UUID, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    component = await _get_component(db, product_id, component_id)
    audit.record(
        db,
        "product.component_removed",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={
            "component_id": str(component.id),
            "before": audit.snapshot(component, COMPONENT_FIELDS),
        },
    )
    await db.delete(component)
    await db.commit()
    return await _product_detail(db, product)


@router.post("/products/{product_id}/price-preview")
async def price_preview(
    product_id: uuid.UUID, body: PricePreviewIn, user: StaffUser, db: DB
) -> PricePreviewOut:
    """Try a product template with sample dimensions. Nothing is saved."""
    product = await get_or_404(db, Product, product_id, "Product")
    width_mm, height_mm = to_mm(body.width, body.unit), to_mm(body.height, body.unit)
    check_dimensions(product, width_mm, height_mm)
    components = await load_components(db, product.id)
    if not components:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Add at least one component to this product"
        )

    settings = await get_pricing_settings(db)
    breakdown = compute_price(
        [to_component_input(c, item) for c, item in components],
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=body.quantity,
        markup_percent=settings.markup_percent,
        vat_percent=settings.vat_percent,
        currency=settings.currency,
    )
    warnings = [f"{item.code} is archived" for _, item in components if not item.is_active]
    if not product.is_active:
        warnings.insert(0, "This product is archived; customers can't select it")
    return PricePreviewOut(**breakdown.as_dict(), warnings=warnings)


# ---------- pricing settings ----------


@router.get("/pricing-settings")
async def read_pricing_settings(user: StaffUser, db: DB) -> PricingSettingsOut:
    return PricingSettingsOut.model_validate(await get_pricing_settings(db))


@router.put("/pricing-settings")
async def update_pricing_settings(
    body: PricingSettingsIn, user: StaffUser, db: DB, request: Request
) -> PricingSettingsOut:
    settings = await get_pricing_settings(db)
    before = audit.snapshot(settings, SETTINGS_FIELDS)
    for field, value in body.model_dump().items():
        setattr(settings, field, value)
    after = audit.snapshot(settings, SETTINGS_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "pricing_settings.updated",
            request=request,
            actor_id=user.id,
            entity="pricing_settings",
            entity_id="1",
            details={"changes": diff},
        )
    await db.commit()
    await db.refresh(settings)
    return PricingSettingsOut.model_validate(settings)
