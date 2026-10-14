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


def material(code: str, unit: str, price: str, category: str = "glass") -> dict[str, Any]:
    return {
        "code": code,
        "name": f"{code} item",
        "category": category,
        "unit": unit,
        "unit_price": price,
    }


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
    """Same template as the worked example in test_pricing.py."""
    glass = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
    frame = await create(admin, "materials", material("AL-FRAME", "lm", "420", "aluminum"))
    track = await create(admin, "materials", material("AL-TRACK", "lm", "180", "aluminum"))
    roller = await create(admin, "materials", material("HW-ROLLER", "piece", "35", "hardware"))
    labor = await create(
        admin,
        "labor-rates",
        {"code": "INSTALL", "name": "Installation", "unit": "sqm", "rate": "650"},
    )
    product = await create(admin, "products", WINDOW)
    pid = product["id"]
    for body in [
        {"material_id": glass["id"], "basis": "area", "factor": "1", "waste_percent": "5"},
        {"material_id": frame["id"], "basis": "perimeter", "factor": "1", "waste_percent": "10"},
        {"material_id": track["id"], "basis": "width", "factor": "2"},
        {"material_id": roller["id"], "basis": "fixed", "factor": "4"},
        {"labor_rate_id": labor["id"], "basis": "area", "factor": "1"},
    ]:
        await create(admin, f"products/{pid}/components", body)
    return pid


async def add_open_back(admin: AsyncClient, pid: str, suffix: str = "") -> dict[str, Any]:
    """Optional add-on: open back aluminum at 300/m plus 100/m to fit it, both around the opening.

    For 1200 x 1000 mm that adds 4.4 m x 400 = 1,760.00 to the cost of one window.
    """
    ob = await create(admin, "materials", material(f"AL-OPENBACK{suffix}", "lm", "300", "aluminum"))
    fit = await create(
        admin,
        "labor-rates",
        {"code": f"FIT-OB{suffix}", "name": "Fit open back", "unit": "lm", "rate": "100"},
    )
    detail = await create(
        admin,
        f"products/{pid}/options",
        {"name": "Open back aluminum", "description": "Extra frame behind the window"},
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
    r = await client.post(f"{API}/materials", json=material("GL-1", "sqm", "1"))
    assert r.status_code == 403


# ---------- materials ----------


async def test_material_create_normalises_code_and_rejects_duplicates(admin: AsyncClient):
    created = await create(admin, "materials", material(" gl-6mm ", "sqm", "850.50"))
    assert created["code"] == "GL-6MM"
    assert created["unit_price"] == "850.50"  # money travels as a string, never a float

    dup = await admin.post(f"{API}/materials", json=material("GL-6MM", "sqm", "1"))
    assert dup.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {"unit_price": "850.123"},
        {"unit_price": "-1"},
        {"unit": "kg"},
        {"code": "no spaces"},
        {"extra": 1},
    ],
)
async def test_material_validation(admin: AsyncClient, bad: dict[str, Any]):
    r = await admin.post(f"{API}/materials", json={**material("GL-1", "sqm", "1"), **bad})
    assert r.status_code == 422


async def test_price_change_is_audited_with_before_and_after(admin: AsyncClient, db: AsyncSession):
    m = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
    r = await admin.patch(f"{API}/materials/{m['id']}", json={"unit_price": "900.00"})
    assert r.status_code == 200 and r.json()["unit_price"] == "900.00"

    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "material.updated"))
    assert entry is not None and entry.details == {"changes": {"unit_price": ["850", "900"]}}


async def test_archive_material(admin: AsyncClient):
    m = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
    r = await admin.patch(f"{API}/materials/{m['id']}", json={"is_active": False})
    assert r.json()["is_active"] is False


# ---------- products & templates ----------


async def test_product_size_range_is_validated(admin: AsyncClient):
    r = await admin.post(f"{API}/products", json={**WINDOW, "min_width_mm": 5000})
    assert r.status_code == 422
    p = await create(admin, "products", WINDOW)
    r = await admin.patch(f"{API}/products/{p['id']}", json={"min_height_mm": 9000})
    assert r.status_code == 422


async def test_component_basis_must_match_item_unit(admin: AsyncClient):
    glass = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
    p = await create(admin, "products", WINDOW)
    r = await admin.post(
        f"{API}/products/{p['id']}/components",
        json={"material_id": glass["id"], "basis": "perimeter", "factor": "1"},
    )
    assert r.status_code == 422 and "per m²" in r.json()["detail"]


async def test_component_needs_exactly_one_item(admin: AsyncClient):
    p = await create(admin, "products", WINDOW)
    r = await admin.post(
        f"{API}/products/{p['id']}/components", json={"basis": "area", "factor": "1"}
    )
    assert r.status_code == 422


async def test_archived_item_cannot_be_added(admin: AsyncClient):
    glass = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
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
    r = await admin.patch(f"{API}/materials/{glass_id}", json={"unit": "lm"})
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
    assert len(r.json()["components"]) == 4


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
        json={"width": "120", "height": "100", "unit": "cm", "quantity": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["width_mm"], body["height_mm"]) == (1200, 1000)
    assert body["unit_subtotal"] == "4455.80"
    assert body["total"] == "11977.19"
    assert (body["rounding"], body["rounded_total"]) == ("22.81", "12000.00")
    assert body["warnings"] == []


async def test_price_preview_rejects_out_of_range_size(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    r = await admin.post(
        f"{API}/products/{pid}/price-preview", json={"width": "10", "height": "100", "unit": "cm"}
    )
    assert r.status_code == 422 and "width must be 300-3000 mm" in r.json()["detail"]


async def test_price_preview_warns_about_archived_items(admin: AsyncClient):
    pid = await build_sliding_window(admin)
    glass_id = (await admin.get(f"{API}/products/{pid}")).json()["components"][0]["material_id"]
    await admin.patch(f"{API}/materials/{glass_id}", json={"is_active": False})
    r = await admin.post(
        f"{API}/products/{pid}/price-preview", json={"width": "120", "height": "100", "unit": "cm"}
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
    m = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
    r = await create(
        admin, "labor-rates", {"code": "INSTALL", "name": "Install", "unit": "sqm", "rate": "650"}
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
    assert len((await admin.get(f"{API}/materials")).json()) == 4  # nothing was removed


async def test_delete_unknown_and_forbidden(
    admin: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await admin.delete(f"{API}/materials/{missing}")).status_code == 404
    m = await create(admin, "materials", material("GL-6MM", "sqm", "850"))
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
    assert sum(c["option_id"] is None for c in detail["components"]) == 5

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
    assert r.json()["options"] == [] and len(r.json()["components"]) == 5  # its lines went too

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
    size = {"width": "120", "height": "100", "unit": "cm", "quantity": 2}
    url = f"{API}/products/{pid}/price-preview"

    plain = (await admin.post(url, json=size)).json()
    assert plain["total"] == "11977.19"  # add-on lines are left out unless chosen
    assert all(line["option"] == "" for line in plain["lines"])

    body = (await admin.post(url, json={**size, "option_ids": [option["id"]]})).json()
    assert body["unit_subtotal"] == "6215.80"  # 4,455.80 + 4.4 m x (300 + 100)
    assert body["total"] == "16708.07" and body["rounded_total"] == "16800.00"
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
