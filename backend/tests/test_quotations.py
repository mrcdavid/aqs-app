"""Quotation flow end to end: customer request -> draft PDF -> admin approve/reject -> final PDF."""

from collections.abc import AsyncIterator
from datetime import date, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models import AuditLog, Role
from app.services.quotations import today_pht
from tests.test_admin_catalog import BUSINESS, build_sliding_window
from tests.test_auth import VALID_PROFILE, fake_google, make_staff, staff_login

API = "/api/v1"
REQUEST = {"width": "120", "height": "100", "unit": "cm", "quantity": 2}


async def new_client() -> AsyncClient:
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    await c.get(f"{API}/health")
    c.headers["X-CSRF-Token"] = c.cookies["aqs_csrf"]
    return c


@pytest.fixture
async def admin(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    await make_staff(db, Role.ADMIN)
    c = await new_client()
    assert (await staff_login(c)).status_code == 200
    yield c
    await c.aclose()


@pytest.fixture
async def product_id(admin: AsyncClient) -> str:
    pid = await build_sliding_window(admin)
    r = await admin.put(
        f"{API}/admin/pricing-settings",
        json={"markup_percent": "20", "vat_percent": "12", "currency": "PHP", **BUSINESS},
    )
    assert r.status_code == 200
    return pid


async def sign_in_customer(
    c: AsyncClient, monkeypatch: pytest.MonkeyPatch, profile: dict[str, Any] | None = None, **claims
) -> None:
    fake_google(monkeypatch, **claims)
    await c.get(f"{API}/auth/google/callback")
    r = await c.put(f"{API}/profile", json=profile or VALID_PROFILE)
    assert r.status_code == 200, r.text


@pytest.fixture
async def customer(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    await sign_in_customer(client, monkeypatch)
    return client


async def request_quote(c: AsyncClient, product_id: str, **overrides: Any) -> dict[str, Any]:
    r = await c.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- happy path ----------


async def test_full_flow(customer: AsyncClient, admin: AsyncClient, product_id: str, db):
    catalog = (await customer.get(f"{API}/catalog/products")).json()
    assert [p["id"] for p in catalog] == [product_id]

    q = await request_quote(customer, product_id)
    assert q["status"] == "pending" and q["number"] is None
    assert (q["width_mm"], q["height_mm"], q["quantity"]) == (1200, 1000, 2)
    assert q["unit_price"] == "5346.96" and q["amount"] == "10693.92"
    assert q["total"] == "11977.19"
    assert len(q["includes"]) == 5
    assert "markup" not in q and "breakdown" not in q  # customers never see internal costs

    draft = await customer.get(f"{API}/quotations/{q['id']}/pdf")
    assert draft.status_code == 200 and draft.headers["content-type"] == "application/pdf"
    assert draft.content.startswith(b"%PDF")

    pending = (await admin.get(f"{API}/admin/quotations", params={"status": "pending"})).json()
    assert [p["id"] for p in pending] == [q["id"]]
    assert pending[0]["customer_city"] == "Quezon City"

    r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"note": "Thank you!"})
    assert r.status_code == 200, r.text
    approved = r.json()
    year = today_pht().year
    assert approved["number"] == f"AQS-{year}-000001"
    assert approved["breakdown"]["markup"] == "1782.32"  # admins see the full breakdown
    assert date.fromisoformat(approved["valid_until"]) == today_pht() + timedelta(days=30)

    mine = (await customer.get(f"{API}/quotations/{q['id']}")).json()
    assert mine["status"] == "approved" and mine["review_note"] == "Thank you!"
    assert mine["can_cancel"] is False

    final = await customer.get(f"{API}/quotations/{q['id']}/pdf")
    assert final.status_code == 200 and final.content.startswith(b"%PDF")
    stored = get_settings().quote_storage_dir / f"AQS-{year}-000001.pdf"
    assert stored.read_bytes() == final.content

    again = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
    assert again.status_code == 409

    actions = (await db.scalars(select(AuditLog.action).order_by(AuditLog.id))).all()
    assert "quotation.created" in actions and "quotation.approved" in actions


async def test_numbers_increment(customer: AsyncClient, admin: AsyncClient, product_id: str):
    numbers = []
    for _ in range(2):
        q = await request_quote(customer, product_id)
        r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
        numbers.append(r.json()["number"])
    assert [n[-6:] for n in numbers] == ["000001", "000002"]


async def test_inch_input(customer: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id, width="48", height="36", unit="in", quantity=1)
    assert (q["width_mm"], q["height_mm"]) == (1219, 914)
    assert (q["input_width"], q["input_unit"]) == ("48.00", "in")


# ---------- prices are frozen ----------


async def test_later_price_change_does_not_alter_quote(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    q = await request_quote(customer, product_id)
    materials = (await admin.get(f"{API}/admin/materials")).json()
    glass = next(m for m in materials if m["code"] == "GL-6MM")
    await admin.patch(f"{API}/admin/materials/{glass['id']}", json={"unit_price": "5000"})

    assert (await customer.get(f"{API}/quotations/{q['id']}")).json()["total"] == "11977.19"
    newer = await request_quote(customer, product_id)
    assert newer["total"] != "11977.19"


# ---------- rules ----------


async def test_profile_required(client: AsyncClient, monkeypatch, product_id: str):
    fake_google(monkeypatch)
    await client.get(f"{API}/auth/google/callback")
    r = await client.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST})
    assert r.status_code == 409 and "profile" in r.json()["detail"]


async def test_archived_items_hide_product(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    materials = (await admin.get(f"{API}/admin/materials")).json()
    await admin.patch(f"{API}/admin/materials/{materials[0]['id']}", json={"is_active": False})
    assert (await customer.get(f"{API}/catalog/products")).json() == []
    r = await customer.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST})
    assert r.status_code == 404


async def test_archived_product_is_not_quotable(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    await admin.patch(f"{API}/admin/products/{product_id}", json={"is_active": False})
    r = await customer.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST})
    assert r.status_code == 404


async def test_size_out_of_range(customer: AsyncClient, product_id: str):
    r = await customer.post(
        f"{API}/quotations", json={"product_id": product_id, **REQUEST, "width": "5000"}
    )
    assert r.status_code == 422 and "width must be" in r.json()["detail"]


@pytest.mark.parametrize(
    "bad", [{"width": "0"}, {"unit": "ft"}, {"quantity": 0}, {"quantity": 101}, {"total": "1"}]
)
async def test_request_validation(customer: AsyncClient, product_id: str, bad: dict[str, Any]):
    r = await customer.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST, **bad})
    assert r.status_code == 422


async def test_pending_limit(customer: AsyncClient, product_id: str, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_pending_quotations", 1)
    await request_quote(customer, product_id)
    r = await customer.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST})
    assert r.status_code == 409 and "too many" in r.json()["detail"]


# ---------- access ----------


async def test_customers_only_see_their_own(
    customer: AsyncClient, product_id: str, monkeypatch: pytest.MonkeyPatch
):
    q = await request_quote(customer, product_id)
    other = await new_client()
    try:
        await sign_in_customer(other, monkeypatch, sub="google-sub-2", email="pedro@up.edu.ph")
        assert (await other.get(f"{API}/quotations/{q['id']}")).status_code == 404
        assert (await other.get(f"{API}/quotations/{q['id']}/pdf")).status_code == 404
        assert (await other.post(f"{API}/quotations/{q['id']}/cancel")).status_code == 404
        assert (await other.get(f"{API}/quotations")).json() == []
    finally:
        await other.aclose()


async def test_roles_are_enforced(customer: AsyncClient, admin: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id)
    r = await customer.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
    assert r.status_code == 403
    r = await admin.post(f"{API}/quotations", json={"product_id": product_id, **REQUEST})
    assert r.status_code == 403


# ---------- cancel / reject ----------


async def test_cancel(customer: AsyncClient, admin: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id)
    r = await customer.post(f"{API}/quotations/{q['id']}/cancel")
    assert r.json()["status"] == "cancelled"
    assert (await customer.post(f"{API}/quotations/{q['id']}/cancel")).status_code == 409
    assert (await customer.get(f"{API}/quotations/{q['id']}/pdf")).status_code == 409
    r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
    assert r.status_code == 409


async def test_reject_requires_note_and_customer_sees_it(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    q = await request_quote(customer, product_id)
    r = await admin.post(f"{API}/admin/quotations/{q['id']}/reject", json={"note": ""})
    assert r.status_code == 422
    r = await admin.post(
        f"{API}/admin/quotations/{q['id']}/reject", json={"note": "Size too large, please call"}
    )
    assert r.json()["status"] == "rejected"
    mine = (await customer.get(f"{API}/quotations/{q['id']}")).json()
    assert mine["review_note"] == "Size too large, please call"


# ---------- PDFs ----------


async def test_pdf_escapes_user_text(
    client: AsyncClient, product_id: str, monkeypatch: pytest.MonkeyPatch
):
    tricky = {**VALID_PROFILE, "full_name": "<b>O'Brien & Sons</b> <para>", "city": "A & B <x>"}
    await sign_in_customer(client, monkeypatch, profile=tricky)
    q = await request_quote(client, product_id)
    r = await client.get(f"{API}/quotations/{q['id']}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


async def test_missing_final_pdf_is_rebuilt(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    q = await request_quote(customer, product_id)
    number = (await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})).json()[
        "number"
    ]
    stored = get_settings().quote_storage_dir / f"{number}.pdf"
    stored.unlink()
    r = await customer.get(f"{API}/quotations/{q['id']}/pdf")
    assert r.status_code == 200 and stored.is_file()
