"""Quotations with several items: one quotation, one PDF, an amount per item and their total."""

# The quotation fixtures are imported by name, which looks like a redefinition to the linter.
# ruff: noqa: F811

from typing import Any

import pytest
import reportlab.rl_config
from httpx import AsyncClient

from app.models import MAX_ITEMS
from tests.test_quotations import (  # noqa: F401 - fixtures
    API,
    REQUEST,
    admin,
    customer,
    product_id,
)

WINDOW = {**REQUEST}  # 120 x 100 cm, quantity 2 -> 12,000.00 (see test_quotations)
SMALL = {"width": "60", "height": "60", "unit": "cm", "quantity": 1}  # -> 2,800.00


def body(product_id: str, *sizes: dict[str, Any]) -> dict[str, Any]:
    return {"items": [{"product_id": product_id, **size} for size in sizes]}


async def create(c: AsyncClient, json: dict[str, Any]) -> dict[str, Any]:
    r = await c.post(f"{API}/quotations", json=json)
    assert r.status_code == 201, r.text
    return r.json()


async def test_two_items_make_one_quotation(
    customer: AsyncClient, admin: AsyncClient, product_id: str, monkeypatch: pytest.MonkeyPatch
):
    q = await create(customer, body(product_id, WINDOW, SMALL))
    assert [i["position"] for i in q["items"]] == [0, 1]
    assert [i["amount"] for i in q["items"]] == ["12000.00", "2800.00"]  # each rounded up
    assert q["subtotal"] == q["total"] == "14800.00" and q["adjustment"] == "0.00"
    assert (q["downpayment"], q["balance"]) == ("7400.00", "7400.00")

    # Lists show every item; admins see each item's own breakdown.
    mine = (await customer.get(f"{API}/quotations")).json()
    assert [i["width_mm"] for i in mine[0]["items"]] == [1200, 600]
    detail = (await admin.get(f"{API}/admin/quotations/{q['id']}")).json()
    assert [i["breakdown"]["rounded_total"] for i in detail["items"]] == ["12000.00", "2800.00"]

    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    pdf = (await customer.get(f"{API}/quotations/{q['id']}/pdf")).content
    for text in (b"12,000.00", b"2,800.00", b"14,800.00", b"7,400.00"):
        assert text in pdf
    assert b"Adjustment" not in pdf


async def test_an_error_says_which_item(customer: AsyncClient, product_id: str):
    r = await customer.post(
        f"{API}/quotations", json=body(product_id, WINDOW, {**SMALL, "width": "5000"})
    )
    assert r.status_code == 422 and r.json()["detail"].startswith("Item 2: width must be")


@pytest.mark.parametrize("count", [0, MAX_ITEMS + 1])
async def test_item_count_limits(customer: AsyncClient, product_id: str, count: int):
    r = await customer.post(f"{API}/quotations", json=body(product_id, *[SMALL] * count))
    assert r.status_code == 422


async def test_changed_total_shows_as_an_adjustment(
    customer: AsyncClient, admin: AsyncClient, product_id: str, monkeypatch: pytest.MonkeyPatch
):
    # The official PDF is saved on approval, so make its text readable before approving.
    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    q = await create(customer, body(product_id, WINDOW, SMALL))
    r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"final_total": "14500"})
    assert r.json()["total"] == "14500.00" and r.json()["total_adjusted"] is True

    mine = (await customer.get(f"{API}/quotations/{q['id']}")).json()
    assert (mine["subtotal"], mine["adjustment"], mine["total"]) == (
        "14800.00",
        "-300.00",
        "14500.00",
    )
    pdf = (await customer.get(f"{API}/quotations/{q['id']}/pdf")).content
    assert b"Subtotal" in pdf and b"Adjustment" in pdf and b"- PHP 300.00" in pdf


async def test_dashboard_counts_a_quotation_once_per_product(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    q = await create(customer, body(product_id, WINDOW, SMALL))
    await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
    d = (await admin.get(f"{API}/admin/dashboard")).json()
    assert [(p["label"], p["approved"], p["approved_value"]) for p in d["by_product"]] == [
        ("Standard sliding window", 1, "14800.00")
    ]
    assert d["top_projects"][0]["product_name"] == "Standard sliding window + 1 more"
