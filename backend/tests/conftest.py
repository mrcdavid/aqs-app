"""Test setup.

DB tests run against `<db>_test` (created by scripts/create_db.py), derived from DATABASE_URL in
backend/.env, or TEST_DATABASE_URL if set. The schema is rebuilt with Alembic once per run and
all tables are truncated before each test. Without a reachable test DB those tests are skipped.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_database_url() -> str | None:
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    app_url = dotenv_values(BACKEND_DIR / ".env").get("DATABASE_URL")
    if not app_url or "CHANGE_ME" in app_url:
        return None
    parts = urlsplit(app_url)
    return urlunsplit(parts._replace(path=parts.path.rstrip("/") + "_test"))


TEST_DATABASE_URL = _test_database_url()

# Must be set before any `app` module is imported. Env vars override backend/.env.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "postgresql+asyncpg://x:x@localhost:5432/none"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["APP_ORIGIN"] = "http://localhost:5173"
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["QUOTE_STORAGE_DIR"] = tempfile.mkdtemp(prefix="aqs-test-quotes-")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

TABLES = (
    "users, profiles, sessions, audit_log, materials, labor_rates, products, product_components, "
    "quotations, quote_counters"
)
# pricing_settings keeps its single row; it is reset to the migration defaults instead.
RESET_SETTINGS = (
    "UPDATE pricing_settings SET markup_percent = 0, vat_percent = 12, currency = 'PHP',"
    " rounding_step = 100, owner_name = 'Cleo David'"
)


async def _can_connect() -> bool:
    import asyncpg

    assert TEST_DATABASE_URL
    try:
        conn = await asyncpg.connect(TEST_DATABASE_URL.replace("+asyncpg", ""), timeout=3)
    except (OSError, asyncpg.PostgresError):
        return False
    await conn.close()
    return True


@pytest.fixture(scope="session")
def migrated_db() -> None:
    if TEST_DATABASE_URL is None:
        pytest.skip("Test DB not configured: set DATABASE_URL in backend/.env")
    if not asyncio.run(_can_connect()):
        pytest.skip("Test DB unreachable: run `uv run python -m scripts.create_db`")

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # Rebuilding from scratch also proves the downgrade path works.
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture
async def db(migrated_db: None) -> AsyncIterator[AsyncSession]:
    limiter.reset()  # every test starts with fresh rate limits (staff logins are 5/min)
    async with SessionLocal() as session:
        # TRUNCATE doesn't fire the audit_log row trigger, so the table can be reset.
        await session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await session.execute(text(RESET_SETTINGS))
        await session.commit()
        yield session


@pytest.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        await c.get("/api/v1/health")  # receive the CSRF cookie
        c.headers["X-CSRF-Token"] = c.cookies["aqs_csrf"]
        yield c
