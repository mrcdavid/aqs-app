"""scripts/reset_staff_password.py: replaces a forgotten staff password."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, Role, User
from app.services.sessions import utcnow
from scripts.reset_staff_password import ResetError, reset_staff_password
from tests.test_auth import STAFF_EMAIL, make_staff, staff_login

NEW = "a-fresh-long-passphrase"


async def test_reset_unlocks_and_new_password_works(client: AsyncClient, db: AsyncSession):
    user = await make_staff(db, Role.SUPER_ADMIN)
    user.locked_until = utcnow() + timedelta(minutes=10)
    user.failed_login_count = 7
    await db.commit()

    await reset_staff_password(db, " OWNER@aqs.example ", NEW)
    await db.commit()

    assert (await staff_login(client)).status_code == 401  # old password no longer works
    r = await client.post("/api/v1/auth/staff/login", json={"email": STAFF_EMAIL, "password": NEW})
    assert r.status_code == 200


async def test_rejects_customers_unknown_and_weak(db: AsyncSession):
    await make_staff(db)
    db.add(
        User(email="c@up.edu.ph", role=Role.USER, auth_provider=AuthProvider.GOOGLE, google_sub="s")
    )
    await db.commit()
    with pytest.raises(ResetError, match="customer"):
        await reset_staff_password(db, "c@up.edu.ph", NEW)
    with pytest.raises(ResetError, match="No staff account"):
        await reset_staff_password(db, "nobody@aqs.example", NEW)
    with pytest.raises(ResetError, match="at least 12"):
        await reset_staff_password(db, STAFF_EMAIL, "short")
