"""Unit tests that need no database."""

import pytest
from fastapi import HTTPException

from app.core.deps import require_role
from app.core.security import (
    hash_password,
    hash_token,
    new_session_token,
    password_problems,
    verify_password,
)
from app.models import AuthProvider, Role, User
from app.services.oauth import GoogleIdentityError, verify_google_identity

GOOD_CLAIMS = {
    "sub": "1234567890",
    "email": "Juan.DelaCruz@UP.edu.ph",
    "email_verified": True,
    "hd": "up.edu.ph",
}


def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse battery")
    assert h.startswith("$argon2id$")
    assert verify_password("correct horse battery", h)[0] is True
    assert verify_password("wrong horse battery", h)[0] is False


def test_password_policy() -> None:
    assert password_problems("short") != []
    assert password_problems("password1234") == ["is too common"]
    assert password_problems("juanito-secret-2026", "juanito@example.com") != []
    assert password_problems("a-long-unique-passphrase") == []


def test_session_tokens_are_random_and_hashed() -> None:
    a, b = new_session_token(), new_session_token()
    assert a != b and len(a) >= 43
    assert len(hash_token(a)) == 32 and hash_token(a) != hash_token(b)


def test_google_identity_accepts_verified_up_email() -> None:
    identity = verify_google_identity(GOOD_CLAIMS, "up.edu.ph")
    assert identity.email == "juan.delacruz@up.edu.ph"
    assert identity.sub == "1234567890"


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"email": "someone@gmail.com", "hd": None}, "domain_not_allowed"),
        ({"hd": "evil.ph"}, "domain_not_allowed"),
        ({"email": "x@up.edu.ph.evil.com"}, "domain_not_allowed"),
        ({"hd": None}, "domain_not_allowed"),  # personal account with a look-alike email
        ({"email_verified": False}, "email_not_verified"),
        ({"email_verified": "true"}, "email_not_verified"),
        ({"sub": None}, "missing_claims"),
    ],
)
def test_google_identity_rejects(override: dict[str, object], reason: str) -> None:
    with pytest.raises(GoogleIdentityError, match=reason):
        verify_google_identity({**GOOD_CLAIMS, **override}, "up.edu.ph")


async def test_require_role() -> None:
    admin = User(email="a@x.ph", role=Role.ADMIN, auth_provider=AuthProvider.PASSWORD)
    customer = User(email="c@up.edu.ph", role=Role.USER, auth_provider=AuthProvider.GOOGLE)
    staff_only = require_role(Role.ADMIN, Role.SUPER_ADMIN)

    assert await staff_only(admin) is admin
    with pytest.raises(HTTPException) as exc:
        await staff_only(customer)
    assert exc.value.status_code == 403
