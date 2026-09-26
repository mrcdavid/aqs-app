"""Admin catalogue API against the real test database."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Role
from tests.test_auth import fake_google, make_staff, staff_login

API = "/api/v1/admin"
BUSINESS = {
    "quote_validity_days": 30,
    "business_name": "Test Glass & Aluminum",
    "business_address": "1 Test St.",
    "business_contact": "0917 000 0000",
    "quote_terms": "Valid for 30 days.",
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
