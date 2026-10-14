"""Auth and profile flows against the real test database."""

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.models import AuditLog, AuthProvider, AuthSession, Role, User
from app.services import oauth as oauth_module
from app.services.sessions import utcnow

STAFF_EMAIL = "owner@aqs.example"
STAFF_PASSWORD = "a-long-unique-passphrase"
SESSION_COOKIE = "aqs_session"

VALID_PROFILE = {
    "full_name": "Juan Dela Cruz",
    "age": 30,
    "contact_number": "09171234567",
    "address_line": "123 Katipunan Ave",
    "city": "Quezon City",
    "province": "Metro Manila",
}


async def make_staff(db: AsyncSession, role: Role = Role.SUPER_ADMIN) -> User:
    user = User(
        email=STAFF_EMAIL,
        role=role,
        auth_provider=AuthProvider.PASSWORD,
        password_hash=hash_password(STAFF_PASSWORD),
    )
    db.add(user)
    await db.commit()
    return user


async def staff_login(client: AsyncClient, password: str = STAFF_PASSWORD) -> Any:
    return await client.post(
        "/api/v1/auth/staff/login", json={"email": STAFF_EMAIL, "password": password}
    )


def fake_google(monkeypatch: pytest.MonkeyPatch, **claims: Any) -> None:
    userinfo = {
        "sub": "google-sub-1",
        "email": "juan@up.edu.ph",
        "email_verified": True,
        "hd": "up.edu.ph",
        **claims,
    }

    async def authorize_access_token(request: Any) -> dict[str, Any]:
        return {"userinfo": userinfo}

    monkeypatch.setattr(oauth_module.oauth.google, "authorize_access_token", authorize_access_token)


# ---------- staff login ----------


async def test_staff_login_sets_httponly_session_cookie(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    r = await staff_login(client)
    assert r.status_code == 200
    assert r.json()["role"] == "super_admin"

    set_cookie = [h for h in r.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE)][0]
    assert "HttpOnly" in set_cookie and "SameSite=lax" in set_cookie

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == STAFF_EMAIL

    # Only the hash of the token is stored.
    stored = await db.scalar(select(AuthSession.token_hash))
    assert stored is not None and client.cookies[SESSION_COOKIE].encode() != stored


async def test_staff_login_wrong_password_is_generic(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    wrong = await staff_login(client, "not-the-password")
    unknown = await client.post(
        "/api/v1/auth/staff/login", json={"email": "nobody@aqs.example", "password": "x"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password"}


async def test_staff_login_requires_csrf_token(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    del client.headers["X-CSRF-Token"]
    assert (await staff_login(client)).status_code == 403


async def test_account_locks_after_repeated_failures(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    limiter.enabled = False
    try:
        for _ in range(10):
            assert (await staff_login(client, "wrong-password")).status_code == 401
        # Correct password is refused while locked.
        assert (await staff_login(client)).status_code == 401
    finally:
        limiter.enabled = True

    locked_until = await db.scalar(select(User.locked_until))
    assert locked_until is not None and locked_until > utcnow()


async def test_staff_login_is_rate_limited(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    codes = [(await staff_login(client, "wrong-password")).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


async def test_google_account_cannot_use_password_login(client: AsyncClient, db: AsyncSession):
    db.add(
        User(
            email=STAFF_EMAIL,
            role=Role.USER,
            auth_provider=AuthProvider.GOOGLE,
            google_sub="sub-x",
        )
    )
    await db.commit()
    assert (await staff_login(client, "anything")).status_code == 401


# ---------- sessions ----------


async def test_logout_revokes_session(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    await staff_login(client)
    stolen_cookie = client.cookies[SESSION_COOKIE]

    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.set(SESSION_COOKIE, stolen_cookie)  # replaying the old cookie must fail
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_staff_session_expires_when_idle(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    await staff_login(client)
    await db.execute(update(AuthSession).values(last_seen_at=utcnow() - timedelta(minutes=31)))
    await db.commit()
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_disabled_user_loses_session(client: AsyncClient, db: AsyncSession):
    user = await make_staff(db)
    await staff_login(client)
    await db.execute(update(User).where(User.id == user.id).values(is_active=False))
    await db.commit()
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_me_without_cookie_is_401(client: AsyncClient):
    assert (await client.get("/api/v1/auth/me")).status_code == 401


# ---------- Google ----------


async def test_google_callback_creates_user_and_redirects_to_profile(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    fake_google(monkeypatch)
    r = await client.get("/api/v1/auth/google/callback")
    assert r.status_code == 303
    assert r.headers["location"] == "http://localhost:5173/app/profile"

    me = (await client.get("/api/v1/auth/me")).json()
    assert me == {**me, "email": "juan@up.edu.ph", "role": "user", "has_profile": False}


async def test_google_callback_rejects_other_domains(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    fake_google(monkeypatch, email="juan@gmail.com", hd=None)
    r = await client.get("/api/v1/auth/google/callback")
    assert r.headers["location"] == "http://localhost:5173/login?error=domain"
    assert await db.scalar(select(User.id)) is None
    assert SESSION_COOKIE not in client.cookies


async def test_google_cannot_take_over_staff_email(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    db.add(
        User(
            email="boss@up.edu.ph",
            role=Role.ADMIN,
            auth_provider=AuthProvider.PASSWORD,
            password_hash=hash_password(STAFF_PASSWORD),
        )
    )
    await db.commit()
    fake_google(monkeypatch, email="boss@up.edu.ph")
    r = await client.get("/api/v1/auth/google/callback")
    assert r.headers["location"] == "http://localhost:5173/login?error=conflict"


# ---------- profile ----------


async def test_profile_setup_flow(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    fake_google(monkeypatch)
    await client.get("/api/v1/auth/google/callback")

    assert (await client.get("/api/v1/profile")).status_code == 404
    r = await client.put("/api/v1/profile", json=VALID_PROFILE)
    assert r.status_code == 200 and r.json() == VALID_PROFILE
    assert (await client.get("/api/v1/auth/me")).json()["has_profile"] is True


@pytest.mark.parametrize(
    "bad",
    [
        {"contact_number": "12345"},
        {"contact_number": "0917123456"},  # one digit short
        {"contact_number": "+1 415 555 0100"},  # not a PH number
        {"contact_number": "(02) 8123 4567"},  # landline, not a mobile
        {"age": 12},
        {"full_name": ""},
        {"full_name": "Juan 2"},  # digits in a name
        {"city": "Quezon City 1"},
        {"province": "<script>"},
        {"is_admin": True},  # unknown fields are rejected
    ],
)
async def test_profile_validation(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, bad: dict
):
    fake_google(monkeypatch)
    await client.get("/api/v1/auth/google/callback")
    r = await client.put("/api/v1/profile", json={**VALID_PROFILE, **bad})
    assert r.status_code == 422


async def test_staff_cannot_use_customer_profile(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    await staff_login(client)
    assert (await client.get("/api/v1/profile")).status_code == 403


# ---------- audit ----------


async def test_audit_log_is_written_and_append_only(client: AsyncClient, db: AsyncSession):
    await make_staff(db)
    await staff_login(client, "wrong-password")
    await staff_login(client)

    actions = (await db.scalars(select(AuditLog.action).order_by(AuditLog.id))).all()
    assert actions == ["login.staff.failed", "login.staff.success"]

    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(text("UPDATE audit_log SET action = 'tampered'"))
    await db.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(text("DELETE FROM audit_log"))
    await db.rollback()


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("0917 123 4567", "09171234567"),
        ("0917-123-4567", "09171234567"),
        ("+63 917 123 4567", "+639171234567"),
        ("(+63) 917.123.4567", "+639171234567"),
    ],
)
async def test_profile_mobile_number_is_cleaned_up(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, typed: str, stored: str
):
    """People type spaces and dashes; we keep only the digits (and the leading +)."""
    fake_google(monkeypatch)
    await client.get("/api/v1/auth/google/callback")
    names = {"full_name": "Ma. Cristina O'Neil-Reyes", "city": "Science City of Muñoz"}
    r = await client.put(
        "/api/v1/profile", json={**VALID_PROFILE, **names, "contact_number": typed}
    )
    assert r.status_code == 200, r.text
    assert r.json()["contact_number"] == stored
    assert r.json()["full_name"] == "Ma. Cristina O'Neil-Reyes"
