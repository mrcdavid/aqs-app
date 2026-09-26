"""Create the `aqs_app` login role and the `aqs` database if they don't exist.

Run once from backend/:  uv run python -m scripts.create_db
Also creates `<db>_test` for the test suite.
Then create tables with:  uv run alembic upgrade head

Reads POSTGRES_ADMIN_URL (your pgAdmin superuser) and DATABASE_URL (the app role) from .env.
The app role is NOT a superuser; it only owns the `aqs` database.
"""

import asyncio
import re
import sys
from urllib.parse import unquote, urlsplit

import asyncpg

from app.core.config import get_settings

IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def sql_literal(value: str) -> str:
    # CREATE ROLE can't take bind parameters, so quote the password safely.
    return "'" + value.replace("'", "''") + "'"


async def main() -> None:
    settings = get_settings()
    if settings.postgres_admin_url is None:
        sys.exit("POSTGRES_ADMIN_URL is not set in backend/.env")

    app_url = urlsplit(settings.database_url.get_secret_value())
    role = unquote(app_url.username or "")
    password = unquote(app_url.password or "")
    db_name = app_url.path.lstrip("/")

    for name in (role, db_name):
        if not IDENT.match(name):
            sys.exit(f"Invalid name {name!r}: use lowercase letters, digits, underscores")
    if len(password) < 16 or "CHANGE_ME" in password:
        sys.exit("Set a real password (16+ chars) for the app role in DATABASE_URL")

    conn = await asyncpg.connect(settings.postgres_admin_url.get_secret_value())
    try:
        if await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
            print(f"Role {role} exists - updating password")
            await conn.execute(f'ALTER ROLE "{role}" WITH PASSWORD {sql_literal(password)}')
        else:
            await conn.execute(
                f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                f"PASSWORD {sql_literal(password)}"
            )
            print(f"Created role {role}")

        # The app database, plus a separate one the test suite can wipe freely.
        for name in (db_name, f"{db_name}_test"):
            if await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
                print(f"Database {name} already exists")
            else:
                await conn.execute(
                    f'CREATE DATABASE "{name}" OWNER "{role}" ENCODING \'UTF8\' TEMPLATE template0'
                )
                print(f"Created database {name} (owner {role})")
    finally:
        await conn.close()

    print("Done. Next: uv run alembic upgrade head")


if __name__ == "__main__":
    asyncio.run(main())
