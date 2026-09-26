"""Create the first super_admin account (there is no public staff sign-up).

Run from backend/:  uv run python -m scripts.create_super_admin
The password is typed at a hidden prompt; it is never passed on the command line or logged.
"""

import asyncio
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.security import hash_password, password_problems
from app.db.session import SessionLocal, engine
from app.models import AuthProvider, Role, User
from app.services import audit


def ask_email() -> str:
    raw = input("Super admin email: ").strip().lower()
    try:
        return TypeAdapter(EmailStr).validate_python(raw)
    except ValidationError:
        sys.exit("Not a valid email address")


def ask_password(email: str) -> str:
    while True:
        password = getpass.getpass("Password (hidden, 12+ chars): ")
        problems = password_problems(password, email)
        if problems:
            print("Password " + "; ".join(problems) + ". Try again.")
            continue
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords don't match. Try again.")
            continue
        return password


async def main() -> None:
    email = ask_email()
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).where(User.email == email)):
            sys.exit(f"An account with {email} already exists")
        password = ask_password(email)
        user = User(
            email=email,
            role=Role.SUPER_ADMIN,
            auth_provider=AuthProvider.PASSWORD,
            password_hash=hash_password(password),
        )
        db.add(user)
        await db.flush()
        audit.record(
            db, "user.created", entity="user", entity_id=user.id, details={"via": "script"}
        )
        await db.commit()
    await engine.dispose()
    print(f"Created super_admin {email}")


if __name__ == "__main__":
    asyncio.run(main())
