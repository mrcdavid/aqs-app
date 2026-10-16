"""Data migrations, checked on real rows (the suite otherwise builds the schema from empty)."""

# The quotation fixtures are imported by name, which looks like a redefinition to the linter.
# ruff: noqa: F811

import asyncio

from alembic.config import Config
from httpx import AsyncClient

from alembic import command
from tests.conftest import BACKEND_DIR
from tests.test_quotations import (  # noqa: F401 - fixtures
    API,
    admin,
    customer,
    product_id,
    request_quote,
)


def _alembic(action: str, revision: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    getattr(command, action)(cfg, revision)


async def migrate(action: str, revision: str) -> None:
    # Alembic's env.py starts its own event loop, so run it outside the test's loop.
    await asyncio.to_thread(_alembic, action, revision)


async def test_0007_keeps_existing_quotations_as_one_item(
    customer: AsyncClient, admin: AsyncClient, product_id: str
):
    q = await request_quote(customer, product_id)
    await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"final_total": "12500"})
    before = (await admin.get(f"{API}/admin/quotations/{q['id']}")).json()

    try:
        await migrate("downgrade", "0006")  # back to one product per quotation...
        await migrate("upgrade", "0007")  # ...and forward again: the row is moved into an item
    finally:
        await migrate("upgrade", "head")

    after = (await admin.get(f"{API}/admin/quotations/{q['id']}")).json()
    assert after == before
    assert len(after["items"]) == 1 and after["items"][0]["amount"] == "12000.00"
    assert (after["total"], after["adjustment"]) == ("12500.00", "500.00")
