"""Admin catalogue API against the real test database."""

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import AuditLog, Role
from tests.test_auth import fake_google, make_staff, staff_login

API = "/api/v1/admin"
BUSINESS = {
    "quote_validity_days": 30,
    "business_name": "Test Glass & Aluminum",
    "business_address": "1 Test St.",
    "business_contact": "0917 000 0000",
    "quote_terms": "Valid for 30 days.",
    "rounding_step": "100",
    "owner_name": "Cleo David",
}


@pytest.fixture
async def admin(client: AsyncClient, db: AsyncSession) -> AsyncClient:
    await make_staff(db, Role.ADMIN)
    assert (await staff_login(client)).status_code == 200
    return client


async def create(client: AsyncClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(f"{API}/{path}", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def material(
    code: str, unit: str, price: str, category: str = "glass", **extra: Any
) -> dict[str, Any]:
    return {
        "code": code,
        "name": f"{code} item",
        "category": category,
        "unit": unit,
        "unit_price": price,
        **extra,
    }


BAR_21FT = {"stock_length": "21", "stock_length_unit": "ft"}


WINDOW = {
    "code": "SW-STD",
    "name": "Standard sliding window",
    "category": "sliding_window",
    "min_width_mm": 300,
    "max_width_mm": 3000,
    "min_height_mm": 300,
    "max_height_mm": 2500,
}


async def build_sliding_window(admin: AsyncClient) -> str:
    """Same template as the worked example in test_pricing.py (a computed product).

    48 x 48 in: cost 5,612.00 per window; +20% markup = 6,734.40; x2 = 13,468.80 -> 13,500.00.
    """
    glass = await create(admin, "materials", material("GL-6MM", "sqft", "45"))
    frame = await create(
        admin, "materials", material("AL-FRAME", "bar", "1850", "aluminum", **BAR_21FT)
    )
    track = await create(admin, "materials", material("AL-TRACK", "ft", "55", "aluminum"))
    roller = await create(admin, "materials", material("HW-ROLLER", "piece", "35", "hardware"))
    rubber = await create(admin, "materials", material("HW-RUBBER", "kg", "320", "hardware"))
    labor = await create(
        admin,
        "labor-rates",
        {"code": "INSTALL", "name": "Installation", "unit": "sqft", "rate": "20"},
    )
    product = await create(admin, "products", WINDOW)
    pid = product["id"]
    for body in [
        {"material_id": glass["id"], "basis": "area", "factor": "1", "waste_percent": "5"},
        {"material_id": frame["id"], "basis": "perimeter", "factor": "2"},
        {"material_id": track["id"], "basis": "width", "factor": "2"},
        {"material_id": roller["id"], "basis": "fixed", "factor": "4"},
        {"material_id": rubber["id"], "basis": "perimeter", "factor": "0.05"},
        {"labor_rate_id": labor["id"], "basis": "area", "factor": "1"},
    ]:
        await create(admin, f"products/{pid}/components", body)
    return pid


async def add_open_back(
    admin: AsyncClient, pid: str, suffix: str = "", reduction_mm: int = 0
) -> dict[str, Any]:
    """Optional add-on: open back aluminum at 90/ft plus 30/ft to fit it, both around the opening.

    For 48 x 48 in that adds 16 ft x 120 = 1,920.00 to the cost of one window.
    """
    ob = await create(admin, "materials", material(f"AL-OPENBACK{suffix}", "ft", "90", "aluminum"))
    fit = await create(
        admin,
        "labor-rates",
        {"code": f"FIT-OB{suffix}", "name": "Fit open back", "unit": "ft", "rate": "30"},
    )
    detail = await create(
        admin,
        f"products/{pid}/options",
        {
            "name": "Open back aluminum",
            "description": "Extra frame behind the window",
            "width_reduction_mm": reduction_mm,
            "height_reduction_mm": reduction_mm,
        },
    )
    option = detail["options"][0]
    for body in [
        {"material_id": ob["id"], "basis": "perimeter", "factor": "1"},
        {"labor_rate_id": fit["id"], "basis": "perimeter", "factor": "1"},
    ]:
        await create(admin, f"products/{pid}/components", {**body, "option_id": option["id"]})
    return option


# ---------- access ----------


async def test_anonymous_and_customers_are_blocked(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    assert (await client.get(f"{API}/materials")).status_code == 401
    fake_google(monkeypatch)
    await client.get("/api/v1/auth/google/callback")
    assert (await client.get(f"{API}/materials")).status_code == 403
    r = await client.post(f"{API}/materials", json=material("GL-1", "sqft", "1"))
    assert r.status_code == 403


# ---------- materials ----------


async def test_material_create_normalises_code_and_rejects_duplicates(admin: AsyncClient):
    created = await create(admin, "materials", material(" gl-6mm ", "sqft", "850.50"))
    assert created["code"] == "GL-6MM"
    assert created["unit_price"] == "850.50"  # money travels as a string, never a float
    assert created["stock_length"] is None

    dup = await admin.post(f"{API}/materials", json=material("GL-6MM", "sqft", "1"))
    assert dup.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {"unit_price": "850.123"},
        {"unit_price": "-1"},
        {"unit": "sqm"},  # metric units are gone since pricing v2
        {"unit": "lm"},
        {"unit": "bar"},  # a bar needs its length
        {"unit": "bar", "stock_length": "21"},
        {"unit": "bar", "stock_length": "0", "stock_length_unit": "ft"},
        {"unit": "bar", "stock_length": "21", "stock_length_unit": "yd"},
        {**BAR_21FT},  # only bars have a length
        {"code": "no spaces"},
        {"extra": 1},
    ],
)
async def test_material_validation(admin: AsyncClient, bad: dict[str, Any]):
    r = await admin.post(f"{API}/materials", json={**material("GL-1", "sqft", "1"), **bad})
    assert r.status_code == 422


async def test_bar_material_keeps_its_length(admin: AsyncClient):
    bar = await create(
        admin,
        "materials",
        material("MS-10SQ", "bar", "450", "metal", stock_length="6", stock_length_unit="m"),
    )
    assert (bar["unit"], bar["stock_length"], bar["stock_length_unit"]) == ("bar", "6.00", "m")
    url = f"{API}/materials/{bar['id']}"
    r = await admin.patch(url, json={"unit_price": "480"})  # the length is kept
    assert (r.json()["unit_price"], r.json()["stock_length"]) == ("480.00", "6.00")
    r = await admin.patch(url, json={"stock_length": "21", "stock_length_unit": "ft"})
    assert (r.json()["stock_length"], r.json()["stock_length_unit"]) == ("21.00", "ft")
    r = await admin.patch(url, json={"unit": "piece"})  # not a bar any more: no length
    assert (r.json()["stock_length"], r.json()["stock_length_unit"]) == (None, None)
    assert (await admin.patch(url, json={"unit": "bar"})).status_code == 422  # length needed
    assert (await admin.patch(url, json={"stock_length": "6"})).status_code == 422


@pytest.mark.parametrize("unit", ["kg", "bar", "sqm"])
async def test_labor_units(admin: AsyncClient, unit: str):
    """Labour is paid per piece, per foot or per sq ft."""
    body = {"code": "INSTALL", "name": "Install", "unit": unit, "rate": "1"}
    assert (await admin.post(f"{API}/labor-rates", json=body)).status_code == 422


async def test_price_change_is_audited_with_before_and_after(admin: AsyncClient, db: AsyncSession):
    m = await create(admin, "materials", material("GL-6MM", "sqft", "850"))
    r = await admin.patch(f"{API}/materials/{m['id']}", json={"unit_price": "900.00"})
    assert r.status_code == 200 and r.json()["unit_price"] == "900.00"

    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "material.updated"))
    assert entry is not None and entry.details == {"changes": {"unit_price": ["850", "900"]}}


async def test_archive_material(admin: AsyncClient):
    m = await create(admin, "materials", material("GL-6MM", "sqft", "850"))
    r = await admin.patch(f"{API}/materials/{m['id']}", json={"is_active": False})
    assert r.json()["is_active"] is False


# ---------- products & templates ----------


async def test_product_size_range_is_validated(admin: AsyncClient):
    r = await admin.post(f"{API}/products", json={**WINDOW, "min_width_mm": 5000})
    assert r.status_code == 422
    p = await create(admin, "products", WINDOW)
    r = await admin.patch(f"{API}/products/{p['id']}", json={"min_height_mm": 9000})
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("unit", "basis", "ok"),
    [
        ("sqft", "area", True),
        ("sqft", "perimeter", False),
        ("ft", "width", True),
        ("ft", "area", False),
        ("piece", "fixed", True),
        ("piece", "height", False),
        ("kg", "perimeter", True),  # kilos per foot, per sq ft or per window
        ("kg", "area", True),
        ("kg", "fixed", True),
        ("bar", "perimeter", True),  # feet needed / bar length
        ("bar", "area", True),  # bars per sq ft (grills)
        ("bar", "fixed", True),
    ],
)
async def test_component_basis_must_fit_item_unit(
    admin: AsyncClient, unit: str, basis: str, ok: bool
):
    extra = BAR_21FT if unit == "bar" else {}
    item = await create(admin, "materials", material("ITEM-1", unit, "10", **extra))
    p = await create(admin, "products", WINDOW)
    r = await admin.post(
        f"{API}/products/{p['id']}/components",
        json={"material_id": item["id"], "basis": basis, "factor": "1"},
    )
    assert r.status_code == (201 if ok else 422), r.text
    if not ok:
        assert "can be measured by" in r.json()["detail"]


async def test_component_needs_exactly_one_item(admin: AsyncClient):
    p = await create(admin, "products", WINDOW)
    r = await admin.post(
        f"{API}/products/{p['id']}/components", json={"basis": "area", "factor": "1"}
    )
    assert r.status_code == 422


async def test_archived_item_cannot_be_added(admin: AsyncClient):
    glass = await create(admin, "materials", material("GL-6MM", "sqft", "850"))
    await admin.patch(f"{API}/materials/{glass['id']}", json={"is_active": False})
    p = await create(admin, "products", WINDOW)
    r = await admin.post(
        f"{API}/products/{p['id']}/components",
        json={"material_id": glass["id"], "basis": "area", "factor": "1"},
    )
    assert r.status_code == 422 and "archived" in r.json()["detail"]


async def test_unit_of_used_material_cannot_change(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    detail = (await admin.get(f"{API}/products/{pid}")).json()
    glass_id = detail["components"][0]["material_id"]
    r = await admin.patch(f"{API}/materials/{glass_id}", json={"unit": "ft"})
    assert r.status_code == 409


async def test_component_of_other_product_is_404(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    component_id = (await admin.get(f"{API}/products/{pid}")).json()["components"][0]["id"]
    other = await create(admin, "products", {**WINDOW, "code": "SW-2"})
    r = await admin.delete(f"{API}/products/{other['id']}/components/{component_id}")
    assert r.status_code == 404


async def test_edit_and_remove_component(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    components = (await admin.get(f"{API}/products/{pid}")).json()["components"]
    r = await admin.patch(
        f"{API}/products/{pid}/components/{components[2]['id']}", json={"factor": "3"}
    )
    assert r.json()["components"][2]["factor"] == "3.0000"
    r = await admin.delete(f"{API}/products/{pid}/components/{components[2]['id']}")
    assert len(r.json()["components"]) == 5


# ---------- pricing ----------


async def test_price_preview_matches_worked_example(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    r = await admin.put(
        f"{API}/pricing-settings",
        json={"markup_percent": "20", "vat_percent": "12", "currency": "php", **BUSINESS},
    )
    assert r.json()["currency"] == "PHP"

    r = await admin.post(
        f"{API}/products/{pid}/price-preview",
        json={"width": "48", "height": "48", "unit": "in", "quantity": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pricing_method"] == "computed"
    assert (body["width_mm"], body["height_mm"], body["area_sqft"]) == (1219, 1219, "16.00")
    frame = body["lines"][1]
    assert (frame["unit"], frame["needed"], frame["quantity"]) == ("bar", "1.5238", "2.0000")
    assert body["unit_subtotal"] == "5612.00"
    assert body["total"] == "13468.80" and body["vat"] == "0.00"  # VAT is included, not added
    assert (body["rounding"], body["rounded_total"]) == ("31.20", "13500.00")
    assert (body["vat_included"], body["margin"]) == ("1446.43", "2276.00")
    assert body["warnings"] == []


async def test_price_preview_rejects_out_of_range_size(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    r = await admin.post(
        f"{API}/products/{pid}/price-preview", json={"width": "4", "height": "48", "unit": "in"}
    )
    assert r.status_code == 422 and "width must be 300-3000 mm" in r.json()["detail"]


async def test_price_preview_warns_about_archived_items(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    glass_id = (await admin.get(f"{API}/products/{pid}")).json()["components"][0]["material_id"]
    await admin.patch(f"{API}/materials/{glass_id}", json={"is_active": False})
    r = await admin.post(
        f"{API}/products/{pid}/price-preview", json={"width": "48", "height": "48", "unit": "in"}
    )
    assert r.json()["warnings"] == ["GL-6MM is archived"]


async def test_pricing_settings_bounds(admin: AsyncClient):
    r = await admin.put(
        f"{API}/pricing-settings",
        json={"markup_percent": "20", "vat_percent": "150", "currency": "PHP", **BUSINESS},
    )
    assert r.status_code == 422


@pytest.mark.parametrize("step", ["-1", "100001", "0.001"])
async def test_rounding_step_bounds(admin: AsyncClient, step: str):
    body = {"markup_percent": "0", "vat_percent": "12", "currency": "PHP", **BUSINESS}
    r = await admin.put(f"{API}/pricing-settings", json={**body, "rounding_step": step})
    assert r.status_code == 422


async def test_settings_put_requires_every_field(admin: AsyncClient):
    """A client that forgets the terms must not silently erase them."""
    partial = {
        "markup_percent": "20",
        "vat_percent": "12",
        "currency": "PHP",
        "quote_validity_days": 30,
        "business_name": "Test Glass",
    }
    r = await admin.put(f"{API}/pricing-settings", json=partial)
    assert r.status_code == 422


# ---------- delete (single item, only when unused) ----------


async def test_delete_unused_material_and_labor_rate(admin: AsyncClient, db: AsyncSession):
    m = await create(admin, "materials", material("GL-6MM", "sqft", "850"))
    r = await create(
        admin, "labor-rates", {"code": "INSTALL", "name": "Install", "unit": "sqft", "rate": "650"}
    )
    assert (await admin.delete(f"{API}/materials/{m['id']}")).status_code == 204
    assert (await admin.delete(f"{API}/labor-rates/{r['id']}")).status_code == 204
    assert (await admin.get(f"{API}/materials")).json() == []
    assert (await admin.get(f"{API}/labor-rates")).json() == []
    actions = (await db.scalars(select(AuditLog.action))).all()
    assert "material.deleted" in actions and "labor_rate.deleted" in actions


async def test_delete_in_use_is_refused(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    components = (await admin.get(f"{API}/products/{pid}")).json()["components"]
    glass_id = components[0]["material_id"]
    labor_id = components[-1]["labor_rate_id"]
    r = await admin.delete(f"{API}/materials/{glass_id}")
    assert r.status_code == 409 and "Standard sliding window" in r.json()["detail"]
    assert (await admin.delete(f"{API}/labor-rates/{labor_id}")).status_code == 409
    assert len((await admin.get(f"{API}/materials")).json()) == 5  # nothing was removed


async def test_delete_unknown_and_forbidden(
    admin: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await admin.delete(f"{API}/materials/{missing}")).status_code == 404
    m = await create(admin, "materials", material("GL-6MM", "sqft", "850"))
    customer = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    await customer.get("/api/v1/health")
    customer.headers["X-CSRF-Token"] = customer.cookies["aqs_csrf"]
    try:
        fake_google(monkeypatch)
        await customer.get("/api/v1/auth/google/callback")
        assert (await customer.delete(f"{API}/materials/{m['id']}")).status_code == 403
    finally:
        await customer.aclose()


# ---------- add-ons ----------


async def test_add_on_lifecycle(admin: AsyncClient, db: AsyncSession):
    pid = await build_sliding_window(admin)
    option = await add_open_back(admin, pid)
    detail = (await admin.get(f"{API}/products/{pid}")).json()
    assert [o["name"] for o in detail["options"]] == ["Open back aluminum"]
    in_option = [c for c in detail["components"] if c["option_id"] == option["id"]]
    assert len(in_option) == 2
    assert sum(c["option_id"] is None for c in detail["components"]) == 6

    r = await admin.patch(
        f"{API}/products/{pid}/options/{option['id']}", json={"name": "Open back frame"}
    )
    assert r.json()["options"][0]["name"] == "Open back frame"

    line_url = f"{API}/products/{pid}/components/{in_option[0]['id']}"

    def option_of(body: dict[str, Any]) -> str | None:
        return next(c for c in body["components"] if c["id"] == in_option[0]["id"])["option_id"]

    r = await admin.patch(line_url, json={"option_id": None})  # move to "always included"
    assert option_of(r.json()) is None
    r = await admin.patch(line_url, json={"option_id": option["id"]})  # and back
    assert option_of(r.json()) == option["id"]
    r = await admin.patch(line_url, json={"factor": "2"})  # leaving option_id out keeps it
    assert option_of(r.json()) == option["id"]

    r = await admin.delete(f"{API}/products/{pid}/options/{option['id']}")
    assert r.status_code == 200
    assert r.json()["options"] == [] and len(r.json()["components"]) == 6  # its lines went too

    actions = set(
        (
            await db.scalars(select(AuditLog.action).where(AuditLog.action.like("product.option%")))
        ).all()
    )
    assert actions == {"product.option_added", "product.option_updated", "product.option_removed"}


async def test_add_on_names_are_unique_per_product(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    await add_open_back(admin, pid)
    r = await admin.post(f"{API}/products/{pid}/options", json={"name": "open back ALUMINUM"})
    assert r.status_code == 409
    r = await admin.post(f"{API}/products/{pid}/options", json={"name": "X"})
    assert r.status_code == 422


async def test_add_on_must_belong_to_the_product(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    option = await add_open_back(admin, pid)
    other = await create(admin, "products", {**WINDOW, "code": "SW-2"})
    glass = next(m for m in (await admin.get(f"{API}/materials")).json() if m["code"] == "GL-6MM")
    body = {"material_id": glass["id"], "basis": "area", "factor": "1", "option_id": option["id"]}
    r = await admin.post(f"{API}/products/{other['id']}/components", json=body)
    assert r.status_code == 404
    r = await admin.patch(
        f"{API}/products/{other['id']}/options/{option['id']}", json={"name": "Nope"}
    )
    assert r.status_code == 404


async def test_price_preview_with_add_on(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    option = await add_open_back(admin, pid)
    await admin.put(
        f"{API}/pricing-settings",
        json={"markup_percent": "20", "vat_percent": "12", "currency": "PHP", **BUSINESS},
    )
    size = {"width": "48", "height": "48", "unit": "in", "quantity": 2}
    url = f"{API}/products/{pid}/price-preview"

    plain = (await admin.post(url, json=size)).json()
    assert plain["total"] == "13468.80"  # add-on lines are left out unless chosen
    assert all(line["option"] == "" for line in plain["lines"])

    body = (await admin.post(url, json={**size, "option_ids": [option["id"]]})).json()
    assert body["unit_subtotal"] == "7532.00"  # 5,612.00 + 16 ft x (90 + 30)
    assert body["total"] == "18076.80" and body["rounded_total"] == "18100.00"
    assert [line["option"] for line in body["lines"]][-2:] == ["Open back aluminum"] * 2

    assert (
        await admin.post(url, json={**size, "option_ids": [str(uuid.uuid4())]})
    ).status_code == 422
    dup = {**size, "option_ids": [option["id"], option["id"]]}
    assert (await admin.post(url, json=dup)).status_code == 422


@pytest.mark.parametrize(("owner", "ok"), [("", True), ("Cleo David", True), ("Cleo 123", False)])
async def test_owner_name_must_be_letters(admin: AsyncClient, owner: str, ok: bool):
    body = {"markup_percent": "0", "vat_percent": "12", "currency": "PHP", **BUSINESS}
    r = await admin.put(f"{API}/pricing-settings", json={**body, "owner_name": owner})
    assert r.status_code == (200 if ok else 422)


# ---------- products sold per sq ft; raising every rate ----------


async def make_per_sqft(admin: AsyncClient, pid: str) -> dict[str, str]:
    """Sell the window per sq ft. Glass type (1/4 Bronze 350 first, Reflective 380), Glass sheet
    (4 x 7 ft first, 4 x 8 ft: recorded, not priced) and an Open back add-on at +40/sq ft.
    Its template stays as the cost guide (5,612.00 for 48 x 48 in). Returns option ids by name.
    """
    r = await admin.patch(f"{API}/products/{pid}", json={"pricing_method": "per_sqft"})
    assert r.status_code == 200 and r.json()["pricing_method"] == "per_sqft"
    ids: dict[str, str] = {}
    groups = (
        ("Glass type", [("1/4 Bronze", "350"), ("Reflective", "380")]),
        ("Glass sheet", [("4 x 7 ft", "0"), ("4 x 8 ft", "0")]),
    )
    for order, (group, choices) in enumerate(groups):
        detail = await create(
            admin, f"products/{pid}/option-groups", {"name": group, "sort_order": order}
        )
        group_id = next(g["id"] for g in detail["option_groups"] if g["name"] == group)
        for n, (name, rate) in enumerate(choices):
            body = {"group_id": group_id, "name": name, "sort_order": n, "rate_per_sqft": rate}
            detail = await create(admin, f"products/{pid}/options", body)
            ids[name] = next(o["id"] for o in detail["options"] if o["name"] == name)
    detail = await create(
        admin, f"products/{pid}/options", {"name": "Open back", "rate_per_sqft": "40"}
    )
    ids["Open back"] = next(o["id"] for o in detail["options"] if o["name"] == "Open back")
    return ids


async def test_per_sqft_price_preview(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    ids = await make_per_sqft(admin, pid)
    chosen = [ids["1/4 Bronze"], ids["4 x 7 ft"], ids["Open back"]]
    size = {"width": "48", "height": "48", "unit": "in", "quantity": 1, "option_ids": chosen}
    r = await admin.post(f"{API}/products/{pid}/price-preview", json=size)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pricing_method"] == "per_sqft"
    assert [(x["name"], x["rate_per_sqft"]) for x in body["rates"]] == [
        ("1/4 Bronze", "350.00"),
        ("Open back", "40.00"),
    ]
    assert (body["area_sqft"], body["rate_per_sqft"]) == ("16.00", "390.00")
    assert (body["unit_price"], body["rounded_total"]) == ("6240.00", "6300.00")  # no markup
    assert body["unit_subtotal"] == "5612.00"  # the cost guide
    assert (body["margin"], body["vat_included"]) == ("688.00", "675.00")
    assert body["warnings"] == []


async def test_per_sqft_product_needs_no_template(admin: AsyncClient):
    p = await create(admin, "products", {**WINDOW, "pricing_method": "per_sqft"})
    url = f"{API}/products/{p['id']}/price-preview"
    size = {"width": "48", "height": "48", "unit": "in"}
    body = (await admin.post(url, json=size)).json()
    assert body["unit_price"] == "0.00"
    assert body["warnings"] == ["No rate per sq ft is set, so the price is 0"]
    await admin.patch(f"{API}/products/{p['id']}", json={"rate_per_sqft": "300"})
    body = (await admin.post(url, json=size)).json()
    assert (body["rounded_total"], body["lines"], body["warnings"]) == ("4800.00", [], [])


@pytest.mark.parametrize("bad", [{"pricing_method": "per_m2"}, {"rate_per_sqft": "-1"}])
async def test_product_pricing_validation(admin: AsyncClient, bad: dict[str, Any]):
    assert (await admin.post(f"{API}/products", json={**WINDOW, **bad})).status_code == 422


async def test_raise_rates(admin: AsyncClient, db: AsyncSession):
    pid = await build_sliding_window(admin)
    await make_per_sqft(admin, pid)
    await admin.patch(f"{API}/products/{pid}", json={"rate_per_sqft": "100"})
    r = await admin.post(f"{API}/pricing/raise-rates", json={"percent": "5"})
    assert r.status_code == 200 and r.json() == {"products": 1, "options": 3}

    detail = (await admin.get(f"{API}/products/{pid}")).json()
    assert detail["rate_per_sqft"] == "105.00"
    assert {o["name"]: o["rate_per_sqft"] for o in detail["options"]} == {
        "1/4 Bronze": "367.50",
        "Reflective": "399.00",
        "4 x 7 ft": "0.00",  # not priced: unchanged
        "4 x 8 ft": "0.00",
        "Open back": "42.00",
    }
    materials = (await admin.get(f"{API}/materials")).json()
    assert next(m for m in materials if m["code"] == "GL-6MM")["unit_price"] == "45.00"

    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "pricing.rates_raised"))
    assert entry is not None and entry.details["percent"] == "5"
    assert entry.details["products"] == [{"product": "SW-STD", "rate": ["100.00", "105.00"]}]
    assert len(entry.details["options"]) == 3

    r = await admin.post(f"{API}/pricing/raise-rates", json={"percent": "-10"})  # and down
    detail = (await admin.get(f"{API}/products/{pid}")).json()
    assert detail["rate_per_sqft"] == "94.50"


@pytest.mark.parametrize("percent", ["0", "-51", "101", "1.234", "abc"])
async def test_raise_rates_bounds(admin: AsyncClient, percent: str):
    r = await admin.post(f"{API}/pricing/raise-rates", json={"percent": percent})
    assert r.status_code == 422
