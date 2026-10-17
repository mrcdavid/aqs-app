"""Data migrations, checked on real rows (the suite otherwise builds the schema from empty)."""

# The quotation fixtures are imported by name, which looks like a redefinition to the linter.
# ruff: noqa: F811

import asyncio

from alembic.config import Config
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
    await admin.post(f"{API}/admin/quotations/{q['id']}/approve", json={"final_total": "14000"})
    before = (await admin.get(f"{API}/admin/quotations/{q['id']}")).json()

    try:
        await migrate("downgrade", "0006")  # back to one product per quotation...
        await migrate("upgrade", "0007")  # ...and forward again: the row is moved into an item
    finally:
        await migrate("upgrade", "head")

    after = (await admin.get(f"{API}/admin/quotations/{q['id']}")).json()
    assert after == before
    assert len(after["items"]) == 1 and after["items"][0]["amount"] == "13500.00"
    assert (after["total"], after["adjustment"]) == ("14000.00", "500.00")


async def _prices(db: AsyncSession) -> dict[str, str]:
    rows = await db.execute(
        text(
            "SELECT code, unit || ' ' || unit_price FROM materials"
            " UNION ALL SELECT code, unit || ' ' || rate FROM labor_rates"
        )
    )
    prices = {code: price for code, price in rows.all()}
    await db.commit()  # release the tables before Alembic alters them
    return prices


async def test_0009_moves_metric_prices_to_feet_and_back(db: AsyncSession):
    """Per m² -> per sq ft and per metre -> per foot at the same cost; kilos and bars have no
    metric equivalent, so going back makes them per piece."""
    try:
        await migrate("downgrade", "0008")
        await db.execute(
            text(
                "INSERT INTO materials (id, code, name, category, unit, unit_price) VALUES"
                " (gen_random_uuid(), 'GL-OLD', 'Glass', 'glass', 'sqm', 850),"
                " (gen_random_uuid(), 'AL-OLD', 'Frame', 'aluminum', 'lm', 420),"
                " (gen_random_uuid(), 'HW-OLD', 'Roller', 'hardware', 'piece', 35)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO labor_rates (id, code, name, unit, rate) VALUES"
                " (gen_random_uuid(), 'IN-OLD', 'Install', 'sqm', 650),"
                " (gen_random_uuid(), 'FIT-OLD', 'Fit', 'lm', 100)"
            )
        )
        await db.commit()

        await migrate("upgrade", "0009")
        assert await _prices(db) == {
            "GL-OLD": "sqft 78.97",  # 850 / 10.7639104
            "AL-OLD": "ft 128.02",  # 420 x 0.3048
            "HW-OLD": "piece 35.00",
            "IN-OLD": "sqft 60.39",
            "FIT-OLD": "ft 30.48",
        }
        await db.execute(
            text(
                "INSERT INTO materials"
                " (id, code, name, category, unit, unit_price, stock_length, stock_length_unit)"
                " VALUES"
                " (gen_random_uuid(), 'RB-NEW', 'Rubber', 'hardware', 'kg', 320, NULL, NULL),"
                " (gen_random_uuid(), 'MS-NEW', 'Square bar', 'metal', 'bar', 450, 6, 'm')"
            )
        )
        await db.commit()

        await migrate("downgrade", "0008")
        assert await _prices(db) == {
            "GL-OLD": "sqm 850.03",  # back within a few centavos
            "AL-OLD": "lm 420.01",
            "HW-OLD": "piece 35.00",
            "IN-OLD": "sqm 650.03",
            "FIT-OLD": "lm 100.00",
            "RB-NEW": "piece 320.00",
            "MS-NEW": "piece 450.00",
        }
    finally:
        await migrate("upgrade", "head")
