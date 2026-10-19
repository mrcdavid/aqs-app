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
from tests.test_admin_catalog import (
    BUSINESS,
    WINDOW,
    add_open_back,
    create,
    make_per_sqft,
    material,
)
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
    """Glass type: Ordinary (40/sq ft) or Reflective (80/sq ft), both measured by area."""
    detail = await create(admin, f"products/{pid}/option-groups", {"name": "Glass type"})
    group_id = detail["option_groups"][0]["id"]
    ids: dict[str, str] = {}
    for name, code, price in (("Ordinary", "GL-ORD", "40"), ("Reflective", "GL-REF", "80")):
        glass = await create(admin, "materials", material(code, "sqft", price))
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
    # 16 sq ft of glass per window, +20% markup, x2 windows, rounded up to the next 100:
    # (5,612 + 640) x 1.2 x 2 = 15,004.80 and (5,612 + 1,280) x 1.2 x 2 = 16,540.80.
    assert (ordinary["total"], reflective["total"]) == ("15100.00", "16600.00")
    item = reflective["items"][0]
    assert item["choices"] == [{"group": "Glass type", "name": "Reflective"}]
    assert item["options"] == [] and len(item["includes"]) == 6

    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    pdf = (await customer.get(f"{API}/quotations/{reflective['id']}/pdf")).content
    assert b"Glass type: Reflective" in pdf and b"16,600.00" in pdf


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
    assert q["total"] == "13500.00"  # same as the plain window


# ---------- every line in a choice: a grill priced by its metal type ----------

GRILL = {**WINDOW, "code": "GRILL", "name": "Metal window grill", "category": "window_grill"}


async def build_grill(admin: AsyncClient) -> tuple[str, str]:
    """Metal type: Solid square bar = 0.25 bars per sq ft (4 x 6-m bars for a 48 x 48 in grill) at
    300 a bar, plus labour 250 per sq ft. Both lines belong to the choice; nothing is always
    included. Returns (product id, choice id)."""
    bar = await create(
        admin,
        "materials",
        material("10MM", "bar", "300", "metal", stock_length="6", stock_length_unit="m"),
    )
    labour = await create(
        admin,
        "labor-rates",
        {"code": "GRILL-SOLID", "name": "Grill labour", "unit": "sqft", "rate": "250"},
    )
    pid = (await create(admin, "products", GRILL))["id"]
    detail = await create(admin, f"products/{pid}/option-groups", {"name": "Metal type"})
    group_id = detail["option_groups"][0]["id"]
    body = {"group_id": group_id, "name": "Solid square bar"}
    solid = (await create(admin, f"products/{pid}/options", body))["options"][0]["id"]
    for line in (
        {"material_id": bar["id"], "basis": "area", "factor": "0.25"},
        {"labor_rate_id": labour["id"], "basis": "area", "factor": "1"},
    ):
        await create(admin, f"products/{pid}/components", {**line, "option_id": solid})
    return pid, solid


@pytest.mark.parametrize(
    ("size", "bars", "total"),
    [
        ("48", "4.0000", "6800.00"),  # (4 x 300 + 16 x 250) x 1.30 = 6,760 -> 6,800
        ("36", "3.0000", "4100.00"),  # 2.25 -> 3 bars: (900 + 9 x 250) x 1.30 = 4,095 -> 4,100
    ],
)
async def test_grill_priced_by_metal_type(
    customer: AsyncClient, admin: AsyncClient, size: str, bars: str, total: str
):
    pid, solid = await build_grill(admin)
    settings = {"markup_percent": "30", "vat_percent": "12", "currency": "PHP", **BUSINESS}
    assert (await admin.put(f"{ADMIN}/pricing-settings", json=settings)).status_code == 200

    grill = next(
        p for p in (await customer.get(f"{API}/catalog/products")).json() if p["id"] == pid
    )
    groups = [(g["name"], [c["name"] for c in g["choices"]]) for g in grill["choice_groups"]]
    assert groups == [("Metal type", ["Solid square bar"])]

    q = await request_quote(customer, pid, width=size, height=size, quantity=1, option_ids=[solid])
    assert q["total"] == total
    assert q["items"][0]["choices"] == [{"group": "Metal type", "name": "Solid square bar"}]
    breakdown = (await admin.get(f"{ADMIN}/quotations/{q['id']}")).json()["items"][0]["breakdown"]
    assert [line["quantity"] for line in breakdown["lines"]][0] == bars  # whole 6-m bars

    size_body = {"width": size, "height": size, "unit": "in", "option_ids": [solid]}
    preview = await admin.post(f"{ADMIN}/products/{pid}/price-preview", json=size_body)
    assert preview.status_code == 200 and preview.json()["rounded_total"] == total


async def test_computed_product_without_lines_is_hidden(customer: AsyncClient, admin: AsyncClient):
    pid = (await create(admin, "products", GRILL))["id"]
    assert all(p["id"] != pid for p in (await customer.get(f"{API}/catalog/products")).json())
    r = await admin.post(
        f"{ADMIN}/products/{pid}/price-preview", json={"width": "48", "height": "48", "unit": "in"}
    )
    assert r.status_code == 422 and r.json()["detail"] == "Add at least one line to this product"
    assert (await customer.post(f"{API}/quotations", json=quote_body(pid))).status_code == 404


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
    sizes = {(line["option"], line["width_in"], line["height_in"]) for line in lines}
    # The window and its glass sit inside the open back; the open back uses the full opening.
    # 100 mm = 3.94 in: 48 in typed -> 44.06 in.
    assert sizes == {
        ("", "44.06", "44.06"),
        ("Ordinary", "44.06", "44.06"),
        ("Open back aluminum", "48.00", "48.00"),
    }

    plain = await request_quote(customer, product_id, option_ids=[glass["Ordinary"]])
    detail = (await admin.get(f"{ADMIN}/quotations/{plain['id']}")).json()
    lines = detail["items"][0]["breakdown"]["lines"]
    assert {(line["width_in"], line["height_in"]) for line in lines} == {("48.00", "48.00")}


async def test_opening_too_small_for_the_open_back(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
    glass: dict[str, str],
):
    open_back = await add_open_back(admin, product_id, reduction_mm=400)
    body = quote_body(
        product_id,
        width="12",  # 12 in (305 mm) is less than the 400 mm the open back takes off
        height="12",
        quantity=1,
        option_ids=[glass["Ordinary"], open_back["id"]],
    )
    r = await customer.post(f"{API}/quotations", json=body)
    assert r.status_code == 422 and "too small" in r.json()["detail"]


async def test_reduction_bounds(admin: AsyncClient, product_id: str):
    body = {"name": "Open back", "width_reduction_mm": 2001}
    r = await admin.post(f"{ADMIN}/products/{product_id}/options", json=body)
    assert r.status_code == 422


# ---------- sold per sq ft (pricing v2) ----------


async def test_per_sqft_window_end_to_end(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    ids = await make_per_sqft(admin, product_id)
    product = (await customer.get(f"{API}/catalog/products")).json()[0]
    groups = [(g["name"], [c["name"] for c in g["choices"]]) for g in product["choice_groups"]]
    assert groups == [
        ("Glass type", ["1/4 Bronze", "Reflective"]),
        ("Glass sheet", ["4 x 7 ft", "4 x 8 ft"]),
    ]
    # Open back has no lines, but a rate: it is offered. Customers never see rates.
    assert product["options"] == [{"id": ids["Open back"], "name": "Open back", "description": ""}]

    chosen = [ids["1/4 Bronze"], ids["4 x 7 ft"], ids["Open back"]]
    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    q = await request_quote(customer, product_id, quantity=1, option_ids=chosen)
    assert q["total"] == "6300.00"  # 16 sq ft x (350 + 40) = 6,240 -> 6,300; no markup added
    item = q["items"][0]
    assert item["choices"] == [
        {"group": "Glass type", "name": "1/4 Bronze"},
        {"group": "Glass sheet", "name": "4 x 7 ft"},
    ]
    assert (item["options"], item["area_sqft"]) == (["Open back"], "16.00")
    pdf = (await customer.get(f"{API}/quotations/{q['id']}/pdf")).content
    for text in (b"Glass sheet: 4 x 7 ft", b"With: Open back", b"16 sq ft", b"6,300.00"):
        assert text in pdf
    assert b"PHP 390.00" not in pdf and b"PHP 350.00" not in pdf  # never the rates

    breakdown = (await admin.get(f"{ADMIN}/quotations/{q['id']}")).json()["items"][0]["breakdown"]
    assert breakdown["pricing_method"] == "per_sqft" and breakdown["rate_per_sqft"] == "390.00"
    assert (breakdown["unit_subtotal"], breakdown["margin"]) == ("5612.00", "688.00")

    reflective = [ids["Reflective"], ids["4 x 8 ft"]]
    q = await request_quote(customer, product_id, quantity=2, option_ids=reflective)
    assert q["total"] == "12200.00"  # 16 x 380 = 6,080 x 2 = 12,160 -> 12,200


async def test_per_sqft_without_any_rate_is_not_offered(
    customer: AsyncClient,
    admin: AsyncClient,
    product_id: str,
):
    await admin.patch(f"{ADMIN}/products/{product_id}", json={"pricing_method": "per_sqft"})
    assert (await customer.get(f"{API}/catalog/products")).json() == []
    r = await customer.post(f"{API}/quotations", json=quote_body(product_id))
    assert (
        r.status_code == 422 and r.json()["detail"] == "This product has no price for these options"
    )


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
