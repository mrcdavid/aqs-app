"""Audit log viewer: staff-only, newest first, filters, pagination."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role
from app.services import audit
from tests.test_auth import fake_google, make_staff, staff_login

API = "/api/v1/admin/audit-log"


@pytest.fixture
async def admin(client: AsyncClient, db: AsyncSession) -> AsyncClient:
    await make_staff(db, Role.ADMIN)
    assert (await staff_login(client)).status_code == 200  # writes login.staff.success
    return client


async def add_entries(db: AsyncSession, *actions: str) -> None:
    for action in actions:
        audit.record(db, action, entity="test")
    await db.commit()


async def test_customers_and_anonymous_are_blocked(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    assert (await client.get(API)).status_code == 401
    fake_google(monkeypatch)
    await client.get("/api/v1/auth/google/callback")
    assert (await client.get(API)).status_code == 403


async def test_newest_first_with_actor_email(admin: AsyncClient, db: AsyncSession):
    await add_entries(db, "material.created")
    body = (await admin.get(API)).json()
    assert [e["action"] for e in body["items"]] == ["material.created", "login.staff.success"]
    assert body["items"][1]["actor_email"] == "owner@aqs.example"
    assert body["next_before_id"] is None


async def test_filters(admin: AsyncClient, db: AsyncSession):
    await add_entries(db, "material.created", "material.updated", "product.created")
    actions = lambda r: [e["action"] for e in r.json()["items"]]  # noqa: E731
    assert actions(await admin.get(API, params={"action": "material"})) == [
        "material.updated",
        "material.created",
    ]
    assert actions(await admin.get(API, params={"actor": "OWNER@"})) == ["login.staff.success"]
    # % must be a literal character, not a wildcard that matches everything.
    assert actions(await admin.get(API, params={"action": "%"})) == []
    assert (
        actions(await admin.get(API, params={"date_from": "2000-01-01", "date_to": "2000-01-02"}))
        == []
    )


async def test_pagination(admin: AsyncClient, db: AsyncSession):
    await add_entries(db, *[f"test.{i}" for i in range(5)])  # 6 entries with the login
    first = (await admin.get(API, params={"limit": 4})).json()
    assert len(first["items"]) == 4 and first["next_before_id"] is not None
    second = (
        await admin.get(API, params={"limit": 4, "before_id": first["next_before_id"]})
    ).json()
    assert len(second["items"]) == 2 and second["next_before_id"] is None
    ids = [e["id"] for e in first["items"] + second["items"]]
    assert ids == sorted(ids, reverse=True) and len(set(ids)) == 6


async def test_limit_is_bounded(admin: AsyncClient):
    assert (await admin.get(API, params={"limit": 1000})).status_code == 422
