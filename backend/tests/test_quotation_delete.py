"""Super admins can delete quotations of any status (soft delete: hidden, kept in the DB)."""

# The quotation fixtures are imported by name, which looks like a redefinition to the linter.
# ruff: noqa: F811

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Quotation, Role, User
from tests.test_auth import STAFF_EMAIL
from tests.test_quotations import (  # noqa: F401 - fixtures
    API,
    admin,
    customer,
    product_id,
    request_quote,
)

ADMIN = f"{API}/admin/quotations"


async def make_super_admin(db: AsyncSession) -> None:
    """The `admin` fixture's account becomes the owner (super admin)."""
    await db.execute(update(User).where(User.email == STAFF_EMAIL).values(role=Role.SUPER_ADMIN))
    await db.commit()


async def test_super_admin_deletes_any_status(
    customer: AsyncClient, admin: AsyncClient, product_id: str, db: AsyncSession
):
    pending, approved, rejected, cancelled = [
        await request_quote(customer, product_id) for _ in range(4)
    ]
    await admin.post(f"{ADMIN}/{approved['id']}/approve", json={})
    await admin.post(f"{ADMIN}/{rejected['id']}/reject", json={"note": "Too large"})
    await customer.post(f"{API}/quotations/{cancelled['id']}/cancel")

    # Plain admins can't delete.
    assert (await admin.delete(f"{ADMIN}/{pending['id']}")).status_code == 403

    await make_super_admin(db)
    for q in (pending, approved, rejected, cancelled):
        assert (await admin.delete(f"{ADMIN}/{q['id']}")).status_code == 204
        # Gone from every page and PDF link, for staff and the customer.
        assert (await admin.get(f"{ADMIN}/{q['id']}")).status_code == 404
        assert (await admin.get(f"{ADMIN}/{q['id']}/pdf")).status_code == 404
        assert (await customer.get(f"{API}/quotations/{q['id']}")).status_code == 404
        assert (await customer.get(f"{API}/quotations/{q['id']}/pdf")).status_code == 404

    assert (await admin.get(ADMIN)).json() == []
    assert (await customer.get(f"{API}/quotations")).json() == []
    dashboard = (await admin.get(f"{API}/admin/dashboard")).json()
    assert (dashboard["approved"], dashboard["rejected"], dashboard["pending_now"]) == (0, 0, 0)

    # Already deleted: nothing to delete. The rows themselves are kept, and audited.
    assert (await admin.delete(f"{ADMIN}/{pending['id']}")).status_code == 404
    kept = await db.scalar(
        select(func.count()).select_from(Quotation).where(Quotation.deleted_at.is_not(None))
    )
    assert kept == 4
    logs = (await db.scalars(select(AuditLog).where(AuditLog.action == "quotation.deleted"))).all()
    assert sorted(log.details["status"] for log in logs) == [
        "approved",
        "cancelled",
        "pending",
        "rejected",
    ]


async def test_deleted_requests_no_longer_count_toward_the_pending_limit(
    customer: AsyncClient, admin: AsyncClient, product_id: str, db: AsyncSession, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_pending_quotations", 1)
    q = await request_quote(customer, product_id)
    await make_super_admin(db)
    await admin.delete(f"{ADMIN}/{q['id']}")
    await request_quote(customer, product_id)  # allowed again


async def test_customers_cannot_delete(customer: AsyncClient, product_id: str):
    q = await request_quote(customer, product_id)
    assert (await customer.delete(f"{ADMIN}/{q['id']}")).status_code == 403
