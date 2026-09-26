"""Set a new password for a staff account (admin or super_admin) from the terminal.

For when the owner forgets their password: passwords are stored as one-way hashes and can't
be recovered, only replaced. Run from backend/:  uv run python -m scripts.reset_staff_password
The new password is typed at a hidden prompt. The account is also unlocked and signed out.
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, password_problems
from app.db.session import SessionLocal, engine
from app.models import AuthProvider, User
from app.services import audit
from app.services.sessions import revoke_user_sessions
from scripts.create_super_admin import ask_password


class ResetError(Exception):
    pass


async def reset_staff_password(db: AsyncSession, email: str, password: str) -> User:
    """Replace the password of an existing, non-deleted staff account (caller commits)."""
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or user.deleted_at is not None:
        raise ResetError(f"No staff account found for {email}")
    if user.auth_provider != AuthProvider.PASSWORD:
        raise ResetError(f"{email} is a customer account (Google sign-in, no password)")
    if problems := password_problems(password, user.email):
        raise ResetError("Password " + "; ".join(problems))
    user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    await revoke_user_sessions(db, user.id)
    audit.record(
        db, "user.password_reset", entity="user", entity_id=user.id, details={"via": "script"}
    )
    return user


async def apply(email: str, password: str) -> None:
    async with SessionLocal() as db:
        try:
            user = await reset_staff_password(db, email, password)
        except ResetError as exc:
            sys.exit(str(exc))
        await db.commit()
        print(f"Password updated for {user.email} ({user.role}). The account is unlocked.")
    await engine.dispose()


def main() -> None:
    # Prompts happen before the event loop starts (input() would block it).
    email = input("Staff email: ").strip().lower()
    password = ask_password(email)
    asyncio.run(apply(email, password))


if __name__ == "__main__":
    main()
