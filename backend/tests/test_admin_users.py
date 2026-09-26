"""User management: super_admin can change accounts; admins can only look."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Role
from tests.test_auth import STAFF_PASSWORD, fake_google, make_staff, staff_login
from tests.test_quotations import new_client

API = "/api/v1/admin"
NEW_EMAIL = "helper@aqs.example"
NEW_PASSWORD = "another-long-passphrase"


async def login_as(email: str, password: str) -> tuple[AsyncClient, int]:
    c = await new_client()
    r = await c.post("/api/v1/auth/staff/login", json={"email": email, "password": password})
    return c, r.status_code


@pytest.fixture
async def owner(client: AsyncClient, db: AsyncSession) -> AsyncClient:
    await make_staff(db, Role.SUPER_ADMIN)
    assert (await staff_login(client)).status_code == 200
    return client


@pytest.fixture
async def helper(owner: AsyncClient) -> AsyncIterator[dict]:
    r = await owner.post(
        f"{API}/users/staff", json={"email": NEW_EMAIL, "role": "admin", "password": NEW_PASSWORD}
    )
    assert r.status_code == 201, r.text
    yield r.json()


async def test_create_staff_and_they_can_log_in(owner: AsyncClient, helper: dict):
    assert helper["role"] == "admin" and helper["auth_provider"] == "password"
    c, code = await login_as(NEW_EMAIL, NEW_PASSWORD)
    await c.aclose()
    assert code == 200


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"email": NEW_EMAIL, "role": "admin", "password": "short"}, 422),
        ({"email": NEW_EMAIL, "role": "admin", "password": "password1234"}, 422),
        ({"email": NEW_EMAIL, "role": "user", "password": NEW_PASSWORD}, 422),
        ({"email": "owner@aqs.example", "role": "admin", "password": NEW_PASSWORD}, 409),
    ],
)
async def test_create_staff_validation(owner: AsyncClient, body: dict, code: int):
    assert (await owner.post(f"{API}/users/staff", json=body)).status_code == code


async def test_disable_signs_out_and_blocks_login(owner: AsyncClient, helper: dict):
    helper_client, _ = await login_as(NEW_EMAIL, NEW_PASSWORD)
    try:
        r = await owner.patch(f"{API}/users/{helper['id']}", json={"is_active": False})
        assert r.json()["is_active"] is False
        assert (await helper_client.get("/api/v1/auth/me")).status_code == 401
        assert (await login_as(NEW_EMAIL, NEW_PASSWORD))[1] == 401

        await owner.patch(f"{API}/users/{helper['id']}", json={"is_active": True})
        assert (await login_as(NEW_EMAIL, NEW_PASSWORD))[1] == 200
    finally:
        await helper_client.aclose()


async def test_role_change(owner: AsyncClient, helper: dict):
    r = await owner.patch(f"{API}/users/{helper['id']}", json={"role": "super_admin"})
    assert r.json()["role"] == "super_admin"


async def test_customers_cannot_become_staff(
    owner: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    customer = await new_client()
    fake_google(monkeypatch)
    await customer.get("/api/v1/auth/google/callback")
    await customer.aclose()
    rows = (await owner.get(f"{API}/users", params={"kind": "customers"})).json()
    r = await owner.patch(f"{API}/users/{rows[0]['id']}", json={"role": "admin"})
    assert r.status_code == 422


async def test_no_changes_to_own_account(owner: AsyncClient):
    me = (await owner.get("/api/v1/auth/me")).json()
    assert (
        await owner.patch(f"{API}/users/{me['id']}", json={"is_active": False})
    ).status_code == 409
    assert (await owner.delete(f"{API}/users/{me['id']}")).status_code == 409


async def test_soft_delete(owner: AsyncClient, helper: dict):
    r = await owner.delete(f"{API}/users/{helper['id']}")
    assert r.json()["deleted_at"] is not None and r.json()["is_active"] is False
    staff = (await owner.get(f"{API}/users", params={"kind": "staff"})).json()
    deleted = (await owner.get(f"{API}/users", params={"kind": "deleted"})).json()
    assert helper["id"] not in [u["id"] for u in staff]
    assert [u["id"] for u in deleted] == [helper["id"]]
    assert (await login_as(NEW_EMAIL, NEW_PASSWORD))[1] == 401
    again = await owner.patch(f"{API}/users/{helper['id']}", json={"is_active": True})
    assert again.status_code == 409


async def test_reset_password(owner: AsyncClient, helper: dict):
    r = await owner.post(
        f"{API}/users/{helper['id']}/reset-password", json={"password": "a-brand-new-passphrase"}
    )
    assert r.status_code == 200
    assert (await login_as(NEW_EMAIL, NEW_PASSWORD))[1] == 401
    assert (await login_as(NEW_EMAIL, "a-brand-new-passphrase"))[1] == 200


async def test_sign_out_everywhere_and_sessions_list(owner: AsyncClient, helper: dict):
    helper_client, _ = await login_as(NEW_EMAIL, NEW_PASSWORD)
    try:
        sessions = (await owner.get(f"{API}/sessions")).json()
        assert sorted(s["email"] for s in sessions) == [NEW_EMAIL, "owner@aqs.example"]
        row = (await owner.get(f"{API}/users", params={"kind": "staff", "q": "helper"})).json()
        assert row[0]["active_sessions"] == 1

        await owner.post(f"{API}/users/{helper['id']}/sign-out")
        assert (await helper_client.get("/api/v1/auth/me")).status_code == 401
    finally:
        await helper_client.aclose()


async def test_admins_can_view_but_not_change(owner: AsyncClient, helper: dict):
    admin_client, _ = await login_as(NEW_EMAIL, NEW_PASSWORD)
    try:
        assert (await admin_client.get(f"{API}/users", params={"kind": "staff"})).status_code == 200
        owner_id = (await owner.get("/api/v1/auth/me")).json()["id"]
        r = await admin_client.patch(f"{API}/users/{owner_id}", json={"is_active": False})
        assert r.status_code == 403
        r = await admin_client.post(
            f"{API}/users/staff",
            json={"email": "x@aqs.example", "role": "admin", "password": NEW_PASSWORD},
        )
        assert r.status_code == 403
        assert (await admin_client.get(f"{API}/sessions")).status_code == 403
    finally:
        await admin_client.aclose()


async def test_changes_are_audited(owner: AsyncClient, helper: dict, db: AsyncSession):
    await owner.patch(f"{API}/users/{helper['id']}", json={"is_active": False})
    actions = (await db.scalars(select(AuditLog.action).order_by(AuditLog.id))).all()
    assert "user.created" in actions and "user.disabled" in actions


def test_staff_password_constant_is_valid() -> None:
    # The fixtures rely on this passing the policy used by create/reset.
    from app.core.security import password_problems

    assert password_problems(STAFF_PASSWORD) == []
