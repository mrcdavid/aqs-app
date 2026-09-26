"""Password hashing (staff), session token generation, and password policy."""

import hashlib
import secrets

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_hasher = PasswordHash((Argon2Hasher(),))

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

# Small built-in deny list; extend with a larger breached-password list if needed.
COMMON_PASSWORDS = frozenset(
    {
        "password1234",
        "password12345",
        "password123456",
        "123456789012",
        "qwertyuiop12",
        "iloveyou1234",
        "admin1234567",
        "administrator",
        "welcome12345",
        "letmein12345",
        "changeme1234",
        "aqsapp123456",
    }
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Returns (valid, new_hash). new_hash is set when the stored hash should be upgraded."""
    return _hasher.verify_and_update(password, password_hash)


# Verified against when the account doesn't exist, so response time doesn't reveal it.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def password_problems(password: str, email: str | None = None) -> list[str]:
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"must be at most {PASSWORD_MAX_LENGTH} characters")
    if password.lower() in COMMON_PASSWORDS:
        problems.append("is too common")
    if email and email.split("@")[0].lower() in password.lower():
        problems.append("must not contain your email name")
    return problems


def new_session_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()
