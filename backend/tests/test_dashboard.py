"""Dashboard figures against real quotations."""

from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.services.quotations import today_pht
from tests.test_quotations import admin, customer, product_id, request_quote  # noqa: F401

API = "/api/v1/admin/dashboard"


async def test_dashboard_counts(customer: AsyncClient, admin: AsyncClient, product_id: str):  # noqa: F811
    approved = await request_quote(customer, product_id)  # 11,977.19 quoted as 12,000.00
    rejected = await request_quote(customer, product_id, quantity=1)
    await request_quote(customer, product_id, width="200")  # stays pending
    r = await admin.post(f"/api/v1/admin/quotations/{approved['id']}/approve", json={})
    assert r.status_code == 200
    r = await admin.post(
        f"/api/v1/admin/quotations/{rejected['id']}/reject", json={"note": "Too large"}
    )
    assert r.status_code == 200

    d = (await admin.get(API)).json()
    # Only the approved quotation counts; rejected is used for the approval rate only.
    assert (d["approved"], d["rejected"]) == (1, 1)
    assert d["approved_value"] == d["average_value"] == "12000.00"
    assert Decimal(d["approval_rate"]) == Decimal("50.0")
    assert d["pending_now"] == 1
    assert "requested" not in d and "pending" not in d

    assert len(d["per_day"]) == 30 and d["per_day"][-1]["day"] == today_pht().isoformat()
    assert d["per_day"][-1] == {
        "day": today_pht().isoformat(),
        "approved": 1,
        "approved_value": "12000.00",
    }
    assert sum(p["approved"] for p in d["per_day"]) == 1

    assert d["by_location"] == [
        {"label": "Metro Manila", "approved": 1, "approved_value": "12000.00"}
    ]
    assert d["by_product"][0]["label"] == "Standard sliding window"
    assert [p["number"] for p in d["top_projects"]] == [f"AQS-{today_pht().year}-000001"]


async def test_date_range(admin: AsyncClient):  # noqa: F811
    old = today_pht() - timedelta(days=400)
    d = (
        await admin.get(
            API,
            params={"date_from": old.isoformat(), "date_to": (old + timedelta(days=6)).isoformat()},
        )
    ).json()
    assert d["approved"] == 0 and len(d["per_day"]) == 7
    assert d["approval_rate"] is None and d["average_value"] is None
    bad = await admin.get(API, params={"date_from": "2026-02-01", "date_to": "2026-01-01"})
    assert bad.status_code == 422
    too_long = await admin.get(API, params={"date_from": "2024-01-01", "date_to": "2026-01-01"})
    assert too_long.status_code == 422


async def test_customers_blocked(customer: AsyncClient):  # noqa: F811
    assert (await customer.get(API)).status_code == 403


@pytest.mark.parametrize("path", ["/api/v1/admin/users", "/api/v1/admin/sessions"])
async def test_anonymous_blocked(client: AsyncClient, db, path: str):
    assert (await client.get(path)).status_code == 401
