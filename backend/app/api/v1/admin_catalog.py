"""Admin catalogue: materials, labour rates, products + templates, pricing settings.

Staff only (admin, super_admin). Nothing here is hard-deleted except template lines and add-ons;
materials, labour rates and products are archived with is_active=false.
Every change is audited with before/after values.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.core.deps import DB, StaffUser
from app.models import (
    LaborRate,
    Material,
    PriceUnit,
    PricingMethod,
    Product,
    ProductComponent,
    ProductOption,
    ProductOptionGroup,
)
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
    OptionGroupIn,
    OptionGroupOut,
    OptionGroupUpdate,
    OptionIn,
    OptionOut,
    OptionUpdate,
    PricePreviewIn,
    PricePreviewOut,
    PricingSettingsIn,
    PricingSettingsOut,
    ProductDetailOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
    RaiseRatesIn,
    RaiseRatesOut,
    check_stock_length,
)
from app.services import audit
from app.services.catalog import (
    check_dimensions,
    ensure_basis_matches,
    ensure_code_free,
    get_option,
    get_or_404,
    get_pricing_settings,
    load_components,
    load_options,
)
from app.services.options import load_groups, pick
from app.services.pricing import money, to_inches, to_mm
from app.services.quotations import breakdown_for

router = APIRouter(prefix="/admin", tags=["admin: catalogue"])

MATERIAL_FIELDS = [
    "code",
    "name",
    "category",
    "unit",
    "unit_price",
    "stock_length",
    "stock_length_unit",
    "is_active",
]
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
    "pricing_method",
    "rate_per_sqft",
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
    "option_id",
]
OPTION_FIELDS = [
    "group_id",
    "name",
    "description",
    "sort_order",
    "width_reduction_mm",
    "height_reduction_mm",
    "rate_per_sqft",
]
GROUP_FIELDS = ["name", "sort_order"]
SETTINGS_FIELDS = [
    "markup_percent",
    "vat_percent",
    "currency",
    "quote_validity_days",
    "business_name",
    "business_address",
    "business_contact",
    "quote_terms",
    "rounding_step",
    "owner_name",
]


def _patch_values(body: Any) -> dict[str, Any]:
    """Fields the client actually sent; null means 'leave unchanged'."""
    return {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}


async def _item_in_use(db: DB, column: Any, item_id: uuid.UUID) -> bool:
    return (
        await db.scalar(select(ProductComponent.id).where(column == item_id).limit(1))
    ) is not None


async def _ensure_deletable(db: DB, column: Any, item_id: uuid.UUID, what: str) -> None:
    """Only items no template uses can be deleted; old quotations keep their frozen prices."""
    names = (
        await db.scalars(
            select(Product.name)
            .join(ProductComponent, ProductComponent.product_id == Product.id)
            .where(column == item_id)
            .distinct()
            .order_by(Product.name)
        )
    ).all()
    if names:
        listed = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This {what} is used in {len(names)} product template(s): {listed}. "
            "Remove it from those templates first, or archive it instead.",
        )


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
    # Bars keep their length unless a new one is sent; other units never have one.
    unit = values.get("unit", material.unit)
    keep = unit == PriceUnit.BAR
    length = values.get("stock_length", material.stock_length if keep else None)
    length_unit = values.get("stock_length_unit", material.stock_length_unit if keep else None)
    try:
        check_stock_length(unit, length, length_unit)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc).capitalize()) from exc
    values |= {"stock_length": length, "stock_length_unit": length_unit}
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


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: uuid.UUID, user: StaffUser, db: DB, request: Request
) -> None:
    material = await get_or_404(db, Material, material_id, "Material")
    await _ensure_deletable(db, ProductComponent.material_id, material.id, "material")
    audit.record(
        db,
        "material.deleted",
        request=request,
        actor_id=user.id,
        entity="material",
        entity_id=material.id,
        details={"before": audit.snapshot(material, MATERIAL_FIELDS)},
    )
    await db.delete(material)
    await db.commit()


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


@router.delete("/labor-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_labor_rate(rate_id: uuid.UUID, user: StaffUser, db: DB, request: Request) -> None:
    rate = await get_or_404(db, LaborRate, rate_id, "Labour rate")
    await _ensure_deletable(db, ProductComponent.labor_rate_id, rate.id, "labour rate")
    audit.record(
        db,
        "labor_rate.deleted",
        request=request,
        actor_id=user.id,
        entity="labor_rate",
        entity_id=rate.id,
        details={"before": audit.snapshot(rate, LABOR_FIELDS)},
    )
    await db.delete(rate)
    await db.commit()


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
                option_id=component.option_id,
                item_code=item.code,
                item_name=item.name,
                item_unit=item.unit,
                item_price=item.unit_price if isinstance(item, Material) else item.rate,
                item_stock_length=item.stock_length if isinstance(item, Material) else None,
                item_stock_length_unit=(
                    item.stock_length_unit if isinstance(item, Material) else None
                ),
                item_active=item.is_active,
                basis=component.basis,
                factor=component.factor,
                waste_percent=component.waste_percent,
                label=component.label,
                sort_order=component.sort_order,
            )
        )
    base = ProductOut.model_validate(product).model_dump()
    groups = [OptionGroupOut.model_validate(g) for g in await load_groups(db, product.id)]
    options = [OptionOut.model_validate(o) for o in await load_options(db, product.id)]
    return ProductDetailOut(**base, option_groups=groups, options=options, components=components)


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
    if body.option_id is not None:
        await get_option(db, product.id, body.option_id)

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
    if "option_id" in body.model_fields_set:
        if body.option_id is not None:
            await get_option(db, product_id, body.option_id)
        values["option_id"] = body.option_id
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
    computed = product.pricing_method == PricingMethod.COMPUTED
    if computed and not any(c.option_id is None for c, _ in components):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Add at least one always-included line to this product",
        )
    picked = pick(
        await load_groups(db, product.id), await load_options(db, product.id), body.option_ids
    )
    chosen = {o.id for o in picked.options}
    used = [(c, item) for c, item in components if c.option_id is None or c.option_id in chosen]

    breakdown = breakdown_for(
        product,
        await get_pricing_settings(db),
        components,
        picked,
        width_in=to_inches(body.width, body.unit),
        height_in=to_inches(body.height, body.unit),
        quantity=body.quantity,
    )
    warnings = [f"{item.code} is archived" for _, item in used if not item.is_active]
    warnings += breakdown.warnings
    if not product.is_active:
        warnings.insert(0, "This product is archived; customers can't select it")
    return PricePreviewOut(**breakdown.as_dict(), warnings=warnings)


# ---------- options: add-ons and the choices of choose-one groups ----------


async def _ensure_option_name_free(
    db: DB,
    product_id: uuid.UUID,
    group_id: uuid.UUID | None,
    name: str,
    *,
    ignore: uuid.UUID | None = None,
) -> None:
    """Add-on names are unique among add-ons; choice names within their group."""
    stmt = select(ProductOption.id).where(
        ProductOption.product_id == product_id,
        ProductOption.group_id.is_(None)
        if group_id is None
        else ProductOption.group_id == group_id,
        func.lower(ProductOption.name) == name.lower(),
    )
    if ignore is not None:
        stmt = stmt.where(ProductOption.id != ignore)
    if await db.scalar(stmt):
        what = "an add-on" if group_id is None else "a choice"
        raise HTTPException(status.HTTP_409_CONFLICT, f"There is already {what} called {name}")


async def _get_group(db: DB, product_id: uuid.UUID, group_id: uuid.UUID) -> ProductOptionGroup:
    group = await db.get(ProductOptionGroup, group_id)
    if group is None or group.product_id != product_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Choice group not found")
    return group


@router.post("/products/{product_id}/options", status_code=status.HTTP_201_CREATED)
async def add_option(
    product_id: uuid.UUID, body: OptionIn, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    if body.group_id is not None:
        await _get_group(db, product.id, body.group_id)
    await _ensure_option_name_free(db, product.id, body.group_id, body.name)
    option = ProductOption(product_id=product.id, **body.model_dump())
    db.add(option)
    await db.flush()
    audit.record(
        db,
        "product.option_added",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={"option_id": str(option.id), "after": audit.snapshot(option, OPTION_FIELDS)},
    )
    await db.commit()
    return await _product_detail(db, product)


@router.patch("/products/{product_id}/options/{option_id}")
async def update_option(
    product_id: uuid.UUID,
    option_id: uuid.UUID,
    body: OptionUpdate,
    user: StaffUser,
    db: DB,
    request: Request,
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    option = await get_option(db, product_id, option_id)
    values = _patch_values(body)
    if "name" in values:
        await _ensure_option_name_free(
            db, product.id, option.group_id, values["name"], ignore=option.id
        )
    before = audit.snapshot(option, OPTION_FIELDS)
    for field, value in values.items():
        setattr(option, field, value)
    after = audit.snapshot(option, OPTION_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "product.option_updated",
            request=request,
            actor_id=user.id,
            entity="product",
            entity_id=product.id,
            details={"option_id": str(option.id), "changes": diff},
        )
    await db.commit()
    return await _product_detail(db, product)


@router.delete("/products/{product_id}/options/{option_id}")
async def remove_option(
    product_id: uuid.UUID, option_id: uuid.UUID, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    """Delete an add-on and its lines. Existing quotations keep their own copy of the prices."""
    product = await get_or_404(db, Product, product_id, "Product")
    option = await get_option(db, product_id, option_id)
    lines = await db.scalar(
        select(func.count())
        .select_from(ProductComponent)
        .where(ProductComponent.option_id == option.id)
    )
    audit.record(
        db,
        "product.option_removed",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={
            "option_id": str(option.id),
            "before": audit.snapshot(option, OPTION_FIELDS),
            "lines_removed": lines or 0,
        },
    )
    await db.delete(option)  # its lines go with it (ON DELETE CASCADE)
    await db.commit()
    return await _product_detail(db, product)


# ---------- choose-one groups (e.g. Glass type) ----------


async def _ensure_group_name_free(
    db: DB, product_id: uuid.UUID, name: str, *, ignore: uuid.UUID | None = None
) -> None:
    stmt = select(ProductOptionGroup.id).where(
        ProductOptionGroup.product_id == product_id,
        func.lower(ProductOptionGroup.name) == name.lower(),
    )
    if ignore is not None:
        stmt = stmt.where(ProductOptionGroup.id != ignore)
    if await db.scalar(stmt):
        raise HTTPException(status.HTTP_409_CONFLICT, f"There is already a group called {name}")


@router.post("/products/{product_id}/option-groups", status_code=status.HTTP_201_CREATED)
async def add_option_group(
    product_id: uuid.UUID, body: OptionGroupIn, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    await _ensure_group_name_free(db, product.id, body.name)
    group = ProductOptionGroup(product_id=product.id, **body.model_dump())
    db.add(group)
    await db.flush()
    audit.record(
        db,
        "product.group_added",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={"group_id": str(group.id), "after": audit.snapshot(group, GROUP_FIELDS)},
    )
    await db.commit()
    return await _product_detail(db, product)


@router.patch("/products/{product_id}/option-groups/{group_id}")
async def update_option_group(
    product_id: uuid.UUID,
    group_id: uuid.UUID,
    body: OptionGroupUpdate,
    user: StaffUser,
    db: DB,
    request: Request,
) -> ProductDetailOut:
    product = await get_or_404(db, Product, product_id, "Product")
    group = await _get_group(db, product_id, group_id)
    values = _patch_values(body)
    if "name" in values:
        await _ensure_group_name_free(db, product.id, values["name"], ignore=group.id)
    before = audit.snapshot(group, GROUP_FIELDS)
    for field, value in values.items():
        setattr(group, field, value)
    after = audit.snapshot(group, GROUP_FIELDS)
    if diff := audit.changes(before, after):
        audit.record(
            db,
            "product.group_updated",
            request=request,
            actor_id=user.id,
            entity="product",
            entity_id=product.id,
            details={"group_id": str(group.id), "changes": diff},
        )
    await db.commit()
    return await _product_detail(db, product)


@router.delete("/products/{product_id}/option-groups/{group_id}")
async def remove_option_group(
    product_id: uuid.UUID, group_id: uuid.UUID, user: StaffUser, db: DB, request: Request
) -> ProductDetailOut:
    """Delete a group with its choices and their lines. Quotations keep their own copy."""
    product = await get_or_404(db, Product, product_id, "Product")
    group = await _get_group(db, product_id, group_id)
    choices = await db.scalar(
        select(func.count()).select_from(ProductOption).where(ProductOption.group_id == group.id)
    )
    audit.record(
        db,
        "product.group_removed",
        request=request,
        actor_id=user.id,
        entity="product",
        entity_id=product.id,
        details={
            "group_id": str(group.id),
            "before": audit.snapshot(group, GROUP_FIELDS),
            "choices_removed": choices or 0,
        },
    )
    await db.delete(group)  # its choices and their lines go with it (ON DELETE CASCADE)
    await db.commit()
    return await _product_detail(db, product)


# ---------- pricing settings ----------


@router.post("/pricing/raise-rates")
async def raise_rates(
    body: RaiseRatesIn, user: StaffUser, db: DB, request: Request
) -> RaiseRatesOut:
    """Raise (or lower) every rate per sq ft by a percentage, e.g. when materials get dearer.

    Covers products' own rates and their options' extras (glass types, open back). Quotations
    already made keep their prices; computed products follow their material prices instead.
    """
    factor = 1 + body.percent / 100
    products = list(
        await db.scalars(
            select(Product)
            .where(Product.rate_per_sqft > 0)
            .order_by(Product.code)
            .with_for_update()
        )
    )
    options = (
        await db.execute(
            select(ProductOption, Product.code)
            .join(Product, Product.id == ProductOption.product_id)
            .where(ProductOption.rate_per_sqft > 0)
            .order_by(Product.code, ProductOption.name)
            .with_for_update(of=ProductOption)
        )
    ).all()
    product_changes, option_changes = [], []
    for product in products:
        before = product.rate_per_sqft
        product.rate_per_sqft = money(before * factor)
        product_changes.append(
            {"product": product.code, "rate": [str(before), str(product.rate_per_sqft)]}
        )
    for option, code in options:
        before = option.rate_per_sqft
        option.rate_per_sqft = money(before * factor)
        option_changes.append(
            {
                "product": code,
                "option": option.name,
                "rate": [str(before), str(option.rate_per_sqft)],
            }
        )
    audit.record(
        db,
        "pricing.rates_raised",
        request=request,
        actor_id=user.id,
        entity="pricing_settings",
        entity_id="1",
        details={
            "percent": str(body.percent),
            "products": product_changes,
            "options": option_changes,
        },
    )
    await db.commit()
    return RaiseRatesOut(products=len(products), options=len(options))


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
