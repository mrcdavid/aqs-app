"""Quotation flow end to end: customer request -> draft PDF -> admin approve/reject -> final PDF."""

import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta
from typing import Any

import pytest
import reportlab.rl_config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models import AuditLog, Role
from app.services.quotations import today_pht
from tests.test_admin_catalog import (
    BUSINESS,
    WINDOW,
    add_open_back,
    build_sliding_window,
    create,
)
from tests.test_auth import STAFF_EMAIL, VALID_PROFILE, fake_google, make_staff, staff_login

API = "/api/v1"
REQUEST = {"width": "120", "height": "100", "unit": "cm", "quantity": 2}
CUSTOMER_EMAIL = "juan@up.edu.ph"  # from fake_google


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


def one(product_id: str, **overrides: Any) -> dict[str, Any]:
    """A request body with one item."""
    return {"items": [{"product_id": product_id, **REQUEST, **overrides}]}


async def request_quote(c: AsyncClient, product_id: str, **overrides: Any) -> dict[str, Any]:
    r = await c.post(f"{API}/quotations", json=one(product_id, **overrides))
    assert r.status_code == 201, r.text
    return r.json()


# ---------- happy path ----------


async def test_full_flow(customer: AsyncClient, admin: AsyncClient, product_id: str, db):
    catalog = (await customer.get(f"{API}/catalog/products")).json()
    assert [p["id"] for p in catalog] == [product_id]

    q = await request_quote(customer, product_id)
    assert q["status"] == "pending" and q["number"] is None
    item = q["items"][0]
    assert (item["width_mm"], item["height_mm"], item["quantity"]) == (1200, 1000, 2)
    assert item["amount"] == "12000.00"  # 11,977.19 rounded up to the next 100
    assert q["total"] == q["subtotal"] == "12000.00" and q["adjustment"] == "0.00"
    assert (q["downpayment"], q["balance"]) == ("6000.00", "6000.00")
    assert len(item["includes"]) == 5
    for hidden in ("markup", "breakdown", "vat", "vat_percent", "unit_price"):
        assert hidden not in q and hidden not in item  # never costs, VAT or unit prices

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
    breakdown = approved["items"][0]["breakdown"]
    assert breakdown["markup"] == "1782.32"  # admins see the full breakdown
    assert breakdown["total"] == "11977.19"
    assert approved["total"] == "12000.00" and approved["total_adjusted"] is False
    assert approved["walk_in"] is False and approved["created_by_email"] == CUSTOMER_EMAIL
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
    item = q["items"][0]
    assert (item["width_mm"], item["height_mm"]) == (1219, 914)
    assert (item["input_width"], item["input_unit"]) == ("48.00", "in")


# ---------- prices are frozen ----------


async def test_later_price_change_does_not_alter_quote(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    q = await request_quote(customer, product_id)
    materials = (await admin.get(f"{API}/admin/materials")).json()
    glass = next(m for m in materials if m["code"] == "GL-6MM")
    await admin.patch(f"{API}/admin/materials/{glass['id']}", json={"unit_price": "5000"})

    assert (await customer.get(f"{API}/quotations/{q['id']}")).json()["total"] == "12000.00"
    newer = await request_quote(customer, product_id)
    assert newer["total"] != "12000.00"


# ---------- rules ----------


async def test_profile_required(client: AsyncClient, monkeypatch, product_id: str):
    fake_google(monkeypatch)
    await client.get(f"{API}/auth/google/callback")
    r = await client.post(f"{API}/quotations", json=one(product_id))
    assert r.status_code == 409 and "profile" in r.json()["detail"]


async def test_archived_items_hide_product(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    materials = (await admin.get(f"{API}/admin/materials")).json()
    await admin.patch(f"{API}/admin/materials/{materials[0]['id']}", json={"is_active": False})
    assert (await customer.get(f"{API}/catalog/products")).json() == []
    r = await customer.post(f"{API}/quotations", json=one(product_id))
    assert r.status_code == 404


async def test_archived_product_is_not_quotable(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    await admin.patch(f"{API}/admin/products/{product_id}", json={"is_active": False})
    r = await customer.post(f"{API}/quotations", json=one(product_id))
    assert r.status_code == 404


async def test_size_out_of_range(customer: AsyncClient, product_id: str):
    r = await customer.post(f"{API}/quotations", json=one(product_id, width="5000"))
    assert r.status_code == 422 and "width must be" in r.json()["detail"]


@pytest.mark.parametrize(
    "bad", [{"width": "0"}, {"unit": "ft"}, {"quantity": 0}, {"quantity": 101}, {"total": "1"}]
)
async def test_request_validation(customer: AsyncClient, product_id: str, bad: dict[str, Any]):
    r = await customer.post(f"{API}/quotations", json=one(product_id, **bad))
    assert r.status_code == 422


async def test_pending_limit(customer: AsyncClient, product_id: str, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_pending_quotations", 1)
    await request_quote(customer, product_id)
    r = await customer.post(f"{API}/quotations", json=one(product_id))
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
    r = await admin.post(f"{API}/quotations", json=one(product_id))
    assert r.status_code == 403


# ---------- cancel / reject ----------


async def test_cancel(customer: AsyncClient, admin: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id)
    r = await customer.post(f"{API}/quotations/{q['id']}/cancel")
    assert r.json()["status"] == "cancelled" and r.json()["cancelled_by_staff"] is False
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
    # Names and places only allow letters now; the street address is still free text.
    tricky = {**VALID_PROFILE, "address_line": "<b>12 O'Brien & Sons</b> <para>"}
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


async def test_pdf_shows_one_amount_payment_terms_and_signatures(
    customer: AsyncClient, admin: AsyncClient, product_id: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)  # readable text in the PDF
    q = await request_quote(customer, product_id)
    draft = (await customer.get(f"{API}/quotations/{q['id']}/pdf")).content
    await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
    final = (await customer.get(f"{API}/quotations/{q['id']}/pdf")).content

    assert b"ESTIMATED AMOUNT" in draft and b"TOTAL AMOUNT" in final
    # The draft watermark is drawn last, i.e. in front of everything (the signatures come last).
    assert draft.rindex(b"PENDING APPROVAL") > draft.rindex(b"Juan Dela Cruz")
    assert b"PENDING APPROVAL" not in final
    for pdf in (draft, final):
        assert b"12,000.00" in pdf  # the rounded amount
        assert b"50% DOWNPAYMENT" in pdf and b"50% UPON COMPLETION AND INSTALLATION" in pdf
        assert b"6,000.00" in pdf
        assert b"Cleo David" in pdf and b"Juan Dela Cruz" in pdf  # owner and client signatures
        # No VAT, exact total or unit price, and no materials or labour (e.g. "GL-6MM item").
        for hidden in (
            b"VAT",
            b"1,283.27",
            b"11,977.19",
            b"5,346.96",
            b"Includes",
            b"GL-6MM",
            b"Installation",
        ):
            assert hidden not in pdf  # no VAT, exact total or unit price


# ---------- adjusting the total on approval ----------


async def test_approve_with_adjusted_total(
    customer: AsyncClient, admin: AsyncClient, product_id: str, db: AsyncSession
):
    q = await request_quote(customer, product_id)
    r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"final_total": "12500"})
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["total"] == "12500.00" and approved["total_adjusted"] is True
    assert approved["subtotal"] == "12000.00" and approved["adjustment"] == "500.00"
    assert approved["items"][0]["amount"] == "12000.00"  # the calculation is kept

    mine = (await customer.get(f"{API}/quotations/{q['id']}")).json()
    assert (mine["total"], mine["downpayment"], mine["balance"]) == (
        "12500.00",
        "6250.00",
        "6250.00",
    )
    log = await db.scalar(select(AuditLog).where(AuditLog.action == "quotation.approved"))
    assert log is not None and log.details["adjusted_from"] == "12000.00"


async def test_odd_total_splits_exactly(customer: AsyncClient, admin: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id)
    await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"final_total": "12000.01"})
    mine = (await customer.get(f"{API}/quotations/{q['id']}")).json()
    assert (mine["downpayment"], mine["balance"]) == ("6000.01", "6000.00")


@pytest.mark.parametrize("bad", ["0", "-5", "12.345", "abc"])
async def test_adjusted_total_validation(
    customer: AsyncClient, admin: AsyncClient, product_id: str, bad: str
):
    q = await request_quote(customer, product_id)
    r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"final_total": bad})
    assert r.status_code == 422


# ---------- staff quoting walk-in clients ----------

CLIENT = {
    "full_name": "Maria Santos",
    "contact_number": "0917 123 4567",
    "address_line": "12 Mabini St., Brgy. Malinis",
    "city": "Pasig",
    "province": "Metro Manila",
}


async def staff_quote(c: AsyncClient, product_id: str, **client: Any) -> dict[str, Any]:
    body = {**one(product_id), "client": {**CLIENT, **client}}
    r = await c.post(f"{API}/admin/quotations", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_staff_quotes_walk_in_client(admin: AsyncClient, product_id: str, db: AsyncSession):
    catalog = (await admin.get(f"{API}/catalog/products")).json()
    assert [p["id"] for p in catalog] == [product_id]  # staff pick from the same products

    q = await staff_quote(admin, product_id)
    assert q["status"] == "pending" and q["walk_in"] is True
    assert q["customer"]["full_name"] == "Maria Santos" and q["customer"]["email"] == ""
    assert q["customer"]["contact_number"] == "09171234567"  # spaces removed
    assert q["created_by_email"] == STAFF_EMAIL
    assert q["total"] == "12000.00" and q["items"][0]["breakdown"]["total"] == "11977.19"

    listed = (await admin.get(f"{API}/admin/quotations", params={"status": "pending"})).json()
    assert [(x["id"], x["walk_in"], x["customer_city"]) for x in listed] == [
        (q["id"], True, "Pasig")
    ]
    draft = await admin.get(f"{API}/admin/quotations/{q['id']}/pdf")
    assert draft.status_code == 200 and draft.content.startswith(b"%PDF")

    r = await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={})
    assert r.json()["status"] == "approved" and r.json()["number"]
    final = await admin.get(f"{API}/admin/quotations/{q['id']}/pdf")
    assert final.status_code == 200 and final.content.startswith(b"%PDF")

    log = await db.scalar(select(AuditLog).where(AuditLog.action == "quotation.created"))
    assert log is not None and log.details["walk_in_client"] == "Maria Santos"


async def test_walk_in_email_is_optional_but_checked(admin: AsyncClient, product_id: str):
    q = await staff_quote(admin, product_id, email="maria@example.com")
    assert q["customer"]["email"] == "maria@example.com"
    assert (await staff_quote(admin, product_id, email=""))["customer"][
        "email"
    ] == ""  # blank = none
    for bad in ("not-an-email", "maria@", "maria@example"):
        body = {**one(product_id), "client": {**CLIENT, "email": bad}}
        assert (await admin.post(f"{API}/admin/quotations", json=body)).status_code == 422


@pytest.mark.parametrize(
    "bad",
    [
        {"contact_number": "call me"},
        {"contact_number": "(02) 8123 4567"},  # landline: a PH mobile number is required
        {"contact_number": "+1 415 555 0100"},  # foreign number
        {"city": ""},
        {"city": "Pasig 2"},
        {"province": "Metro Manila!"},
        {"full_name": "M"},
        {"full_name": "Maria 123"},
        {"age": 30},  # unknown field
    ],
)
async def test_walk_in_client_validation(admin: AsyncClient, product_id: str, bad: dict[str, Any]):
    body = {**one(product_id), "client": {**CLIENT, **bad}}
    assert (await admin.post(f"{API}/admin/quotations", json=body)).status_code == 422


async def test_walk_in_size_rules_apply(admin: AsyncClient, product_id: str):
    body = {**one(product_id, width="5000"), "client": CLIENT}
    r = await admin.post(f"{API}/admin/quotations", json=body)
    assert r.status_code == 422 and "width must be" in r.json()["detail"]


async def test_only_staff_quote_for_others(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    body = {**one(product_id), "client": CLIENT}
    assert (await customer.post(f"{API}/admin/quotations", json=body)).status_code == 403
    await staff_quote(admin, product_id)
    assert (await customer.get(f"{API}/quotations")).json() == []  # not in anyone's account


# ---------- add-ons ----------


@pytest.fixture
async def open_back_id(admin: AsyncClient, product_id: str) -> str:
    return (await add_open_back(admin, product_id))["id"]


async def test_add_on_is_offered_and_priced(
    customer: AsyncClient, product_id: str, open_back_id: str, monkeypatch: pytest.MonkeyPatch
):
    catalog = (await customer.get(f"{API}/catalog/products")).json()
    assert catalog[0]["options"] == [
        {
            "id": open_back_id,
            "name": "Open back aluminum",
            "description": "Extra frame behind the window",
        }
    ]

    plain = await request_quote(customer, product_id)
    assert plain["total"] == "12000.00" and plain["items"][0]["options"] == []
    extra = await request_quote(customer, product_id, option_ids=[open_back_id])
    assert extra["total"] == "16800.00"
    assert extra["items"][0]["options"] == ["Open back aluminum"]
    assert len(extra["items"][0]["includes"]) == 5  # the add-on is listed separately

    monkeypatch.setattr(reportlab.rl_config, "pageCompression", 0)
    pdf = (await customer.get(f"{API}/quotations/{extra['id']}/pdf")).content
    assert b"With: Open back aluminum" in pdf and b"16,800.00" in pdf
    assert b"VAT" not in pdf


async def test_admin_sees_add_on_lines(
    customer: AsyncClient, admin: AsyncClient, product_id: str, open_back_id: str
):
    q = await request_quote(customer, product_id, option_ids=[open_back_id])
    detail = (await admin.get(f"{API}/admin/quotations/{q['id']}")).json()
    options = [line["option"] for line in detail["items"][0]["breakdown"]["lines"]]
    assert options.count("Open back aluminum") == 2 and options.count("") == 5


async def test_walk_in_quote_with_add_on(admin: AsyncClient, product_id: str, open_back_id: str):
    body = {**one(product_id, option_ids=[open_back_id]), "client": CLIENT}
    r = await admin.post(f"{API}/admin/quotations", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["items"][0]["options"] == ["Open back aluminum"]
    assert r.json()["total"] == "16800.00"


async def test_bad_add_ons_are_rejected(
    customer: AsyncClient, admin: AsyncClient, product_id: str, open_back_id: str
):
    other = (await create(admin, "products", {**WINDOW, "code": "SW-2"}))["id"]
    foreign = (await add_open_back(admin, other, suffix="-2"))["id"]
    for option_ids in ([str(uuid.uuid4())], [foreign]):
        r = await customer.post(
            f"{API}/quotations",
            json=one(product_id, option_ids=option_ids),
        )
        assert r.status_code == 422 and r.json()["detail"] == "This option is not available"
    twice = one(product_id, option_ids=[open_back_id, open_back_id])
    assert (await customer.post(f"{API}/quotations", json=twice)).status_code == 422


async def test_archived_add_on_item_hides_only_the_add_on(
    customer: AsyncClient, admin: AsyncClient, product_id: str, open_back_id: str
):
    materials = (await admin.get(f"{API}/admin/materials")).json()
    ob = next(m for m in materials if m["code"] == "AL-OPENBACK")
    await admin.patch(f"{API}/admin/materials/{ob['id']}", json={"is_active": False})

    catalog = (await customer.get(f"{API}/catalog/products")).json()
    assert [p["id"] for p in catalog] == [product_id] and catalog[0]["options"] == []
    body = one(product_id, option_ids=[open_back_id])
    assert (await customer.post(f"{API}/quotations", json=body)).status_code == 422
    await request_quote(customer, product_id)  # the window itself can still be quoted


async def test_empty_add_on_is_not_offered(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    r = await admin.post(f"{API}/admin/products/{product_id}/options", json={"name": "Grill"})
    assert r.status_code == 201
    assert (await customer.get(f"{API}/catalog/products")).json()[0]["options"] == []


# ---------- staff cancelling pending requests ----------


async def test_staff_can_cancel_a_pending_request(
    customer: AsyncClient, admin: AsyncClient, product_id: str, db: AsyncSession
):
    q = await request_quote(customer, product_id)
    url = f"{API}/admin/quotations/{q['id']}"
    r = await admin.post(f"{url}/cancel", json={"note": "Client changed their mind"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled" and r.json()["reviewed_by_email"] == STAFF_EMAIL

    mine = (await customer.get(f"{API}/quotations/{q['id']}")).json()
    assert mine["status"] == "cancelled" and mine["cancelled_by_staff"] is True
    assert mine["review_note"] == "Client changed their mind" and mine["can_cancel"] is False

    # Only pending requests can be cancelled, and a cancelled one can't be approved or printed.
    assert (await admin.post(f"{url}/cancel", json={})).status_code == 409
    assert (await admin.post(f"{url}/approve", json={})).status_code == 409
    assert (await customer.get(f"{API}/quotations/{q['id']}/pdf")).status_code == 409

    log = await db.scalar(select(AuditLog).where(AuditLog.action == "quotation.cancelled"))
    assert log is not None and log.details == {"by": "staff"}


async def test_staff_can_cancel_a_walk_in_quote_without_a_reason(
    admin: AsyncClient, product_id: str
):
    q = await staff_quote(admin, product_id)
    r = await admin.post(f"{API}/admin/quotations/{q['id']}/cancel", json={})
    assert r.json()["status"] == "cancelled" and r.json()["review_note"] is None


async def test_customers_cannot_use_the_staff_cancel(customer: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id)
    r = await customer.post(f"{API}/admin/quotations/{q['id']}/cancel", json={})
    assert r.status_code == 403
