"""Choose-one groups (e.g. Glass type) and add-ons that make the window smaller (open back)."""

# The quotation fixtures are imported by name, which looks like a redefinition to the linter.
# ruff: noqa: F811

from typing import Any

import pytest
import reportlab.rl_config
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from tests.test_admin_catalog import WINDOW, add_open_back, create, material
from tests.test_quotations import (  # noqa: F401 - fixtures
    API,
    REQUEST,
    admin,
    customer,
    product_id,
    request_quote,
)

ADMIN = f"{API}/admin"


async def add_glass_group(admin: AsyncClient, pid: str) -> dict[str, str]:
    """Glass type: Ordinary (500/m²) or Reflective (900/m²), both measured by area."""
    detail = await create(admin, f"products/{pid}/option-groups", {"name": "Glass type"})
    group_id = detail["option_groups"][0]["id"]
    ids: dict[str, str] = {}
    for name, code, price in (("Ordinary", "GL-ORD", "500"), ("Reflective", "GL-REF", "900")):
        glass = await create(admin, "materials", material(code, "sqm", price))
        body = {"group_id": group_id, "name": name, "sort_order": len(ids)}
        detail = await create(admin, f"products/{pid}/options", body)
        option_id = next(o["id"] for o in detail["options"] if o["name"] == name)
        line = {"material_id": glass["id"], "basis": "area", "factor": "1", "option_id": option_id}
        await create(admin, f"products/{pid}/components", line)
        ids[name] = option_id
    return ids


@pytest.fixture
async def glass(admin: AsyncClient, product_id: str) -> dict[str, str]:
    return await add_glass_group(admin, product_id)


def quote_body(product_id: str, **overrides: Any) -> dict[str, Any]:
    return {"items": [{"product_id": product_id, **REQUEST, **overrides}]}


# ---------- choose-one groups ----------


async def test_catalog_lists_choice_groups(
    customer: AsyncClient,
    product_id: str,
    glass: dict[str, str],
):
    product = (await customer.get(f"{API}/catalog/products")).json()[0]
    groups = [(g["name"], [c["name"] for c in g["choices"]]) for g in product["choice_groups"]]
    assert groups == [("Glass type", ["Ordinary", "Reflective"])]
    assert product["options"] == []  # no add-ons


async def test_exactly_one_choice_is_required(
    customer: AsyncClient,
    product_id: str,
    glass: dict[str, str],
):
    r = await customer.post(f"{API}/quotations", json=quote_body(product_id))
    assert r.status_code == 422 and r.json()["detail"] == "Choose one option for Glass type"
    both = quote_body(product_id, option_ids=list(glass.values()))
    assert (await customer.post(f"{API}/quotations", json=both)).status_code == 422


async def test_each_choice_has_its_own_price(
    customer: AsyncClient,
    product_id: str,
    glass: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    ordinary = await request_quote(customer, product_id, option_ids=[glass["Ordinary"]])
    reflective = await request_quote(customer, product_id, option_ids=[glass["Reflective"]])
    # 1.2 m² of glass per window, x2 windows, +20% markup, +12% VAT, rounded up to the next 100.
    assert (ordinary["total"], reflective["total"]) == ("13600.00", "14900.00")
    item = reflective["items"][0]
    assert item["choices"] == [{"group": "Glass type", "name": "Reflective"}]
    assert item["options"] == [] and len(item["includes"]) == 5

    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    pdf = (await customer.get(f"{API}/quotations/{reflective['id']}/pdf")).content
    assert b"Glass type: Reflective" in pdf and b"14,900.00" in pdf


async def test_archived_glass_hides_the_choice_then_the_product(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
    glass: dict[str, str],
):
    codes = {m["code"]: m["id"] for m in (await admin.get(f"{ADMIN}/materials")).json()}
    await admin.patch(f"{ADMIN}/materials/{codes['GL-REF']}", json={"is_active": False})
    product = (await customer.get(f"{API}/catalog/products")).json()[0]
    assert [c["name"] for c in product["choice_groups"][0]["choices"]] == ["Ordinary"]
    r = await customer.post(
        f"{API}/quotations", json=quote_body(product_id, option_ids=[glass["Reflective"]])
    )
    assert r.status_code == 422 and r.json()["detail"] == "This option is not available"

    # No glass left to offer: the window can't be quoted at all.
    await admin.patch(f"{ADMIN}/materials/{codes['GL-ORD']}", json={"is_active": False})
    assert (await customer.get(f"{API}/catalog/products")).json() == []
    r = await customer.post(
        f"{API}/quotations", json=quote_body(product_id, option_ids=[glass["Ordinary"]])
    )
    assert r.status_code == 404


async def test_a_choice_may_have_no_lines(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
):
    detail = await create(admin, f"products/{product_id}/option-groups", {"name": "Grill"})
    group_id = detail["option_groups"][0]["id"]
    detail = await create(
        admin, f"products/{product_id}/options", {"group_id": group_id, "name": "None"}
    )
    none_id = detail["options"][0]["id"]
    q = await request_quote(customer, product_id, option_ids=[none_id])
    assert q["items"][0]["choices"] == [{"group": "Grill", "name": "None"}]
    assert q["total"] == "12000.00"  # same as the plain window


# ---------- open back: the size typed is the wall opening ----------


async def test_open_back_makes_the_window_smaller(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
    glass: dict[str, str],
):
    open_back = await add_open_back(admin, product_id, reduction_mm=100)
    q = await request_quote(customer, product_id, option_ids=[glass["Ordinary"], open_back["id"]])
    detail = (await admin.get(f"{ADMIN}/quotations/{q['id']}")).json()
    lines = detail["items"][0]["breakdown"]["lines"]
    sizes = {(line["option"], line["width_mm"], line["height_mm"]) for line in lines}
    # The window and its glass sit inside the open back; the open back uses the full opening.
    assert sizes == {("", 1100, 900), ("Ordinary", 1100, 900), ("Open back aluminum", 1200, 1000)}

    plain = await request_quote(customer, product_id, option_ids=[glass["Ordinary"]])
    detail = (await admin.get(f"{ADMIN}/quotations/{plain['id']}")).json()
    lines = detail["items"][0]["breakdown"]["lines"]
    assert {(line["width_mm"], line["height_mm"]) for line in lines} == {(1200, 1000)}


async def test_opening_too_small_for_the_open_back(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
    glass: dict[str, str],
):
    open_back = await add_open_back(admin, product_id, reduction_mm=400)
    body = quote_body(
        product_id,
        width="30",
        height="30",
        quantity=1,
        option_ids=[glass["Ordinary"], open_back["id"]],
    )
    r = await customer.post(f"{API}/quotations", json=body)
    assert r.status_code == 422 and "too small" in r.json()["detail"]


async def test_reduction_bounds(admin: AsyncClient, product_id: str):
    body = {"name": "Open back", "width_reduction_mm": 2001}
    r = await admin.post(f"{ADMIN}/products/{product_id}/options", json=body)
    assert r.status_code == 422


# ---------- managing groups ----------


async def test_group_management(admin: AsyncClient, product_id: str, db: AsyncSession):
    url = f"{ADMIN}/products/{product_id}"
    glass = (await create(admin, f"products/{product_id}/option-groups", {"name": "Glass type"}))[
        "option_groups"
    ][0]
    assert (
        await admin.post(f"{url}/option-groups", json={"name": "GLASS TYPE"})
    ).status_code == 409

    r = await admin.patch(f"{url}/option-groups/{glass['id']}", json={"name": "Glass"})
    assert r.json()["option_groups"][0]["name"] == "Glass"

    # The same choice name may be used in two groups, but only once per group.
    grill = next(
        g
        for g in (await create(admin, f"products/{product_id}/option-groups", {"name": "Grill"}))[
            "option_groups"
        ]
        if g["name"] == "Grill"
    )
    for group in (glass, grill):
        await create(
            admin, f"products/{product_id}/options", {"group_id": group["id"], "name": "None"}
        )
    twice = {"group_id": grill["id"], "name": "none"}
    assert (await admin.post(f"{url}/options", json=twice)).status_code == 409

    # A group of another product can't be used.
    other = await create(admin, "products", {**WINDOW, "code": "SW-2"})
    r = await admin.post(
        f"{ADMIN}/products/{other['id']}/options", json={"group_id": glass["id"], "name": "X1"}
    )
    assert r.status_code == 404

    r = await admin.delete(f"{url}/option-groups/{glass['id']}")
    assert [g["name"] for g in r.json()["option_groups"]] == ["Grill"]
    assert [o["group_id"] for o in r.json()["options"]] == [grill["id"]]  # its choice went too

    actions = set(
        (
            await db.scalars(select(AuditLog.action).where(AuditLog.action.like("product.group%")))
        ).all()
    )
    assert actions == {"product.group_added", "product.group_updated", "product.group_removed"}
