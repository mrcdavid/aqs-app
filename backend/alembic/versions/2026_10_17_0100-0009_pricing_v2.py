"""pricing v2: buying units (piece, kg, ft, sq ft, bar), per-sq-ft selling rates

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-17 01:00:00

Written by hand. Existing materials and labour rates move to imperial units at the same cost:
per m² -> per sq ft (price / 10.7639104), per metre -> per foot (price x 0.3048), rounded to
centavos. Template lines keep their basis and factor (area x price/sq ft = area x price/m²).
Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQFT_PER_SQM = "10.7639104"
FT_IN_M = "0.3048"
NEW_UNITS = "('piece', 'kg', 'ft', 'sqft', 'bar')"
OLD_UNITS = "('sqm', 'lm', 'piece')"
PRICE = {"materials": "unit_price", "labor_rates": "rate"}


def upgrade() -> None:
    for table, price in PRICE.items():
        op.drop_constraint(op.f(f"ck_{table}_unit"), table, type_="check")
        op.execute(
            f"UPDATE {table} SET unit = 'sqft', {price} = ROUND({price} / {SQFT_PER_SQM}, 2)"  # noqa: S608 - constants
            " WHERE unit = 'sqm'"
        )
        op.execute(
            f"UPDATE {table} SET unit = 'ft', {price} = ROUND({price} * {FT_IN_M}, 2)"  # noqa: S608 - constants
            " WHERE unit = 'lm'"
        )
        op.create_check_constraint(op.f(f"ck_{table}_unit"), table, f"unit IN {NEW_UNITS}")

    op.add_column("materials", sa.Column("stock_length", sa.Numeric(8, 2), nullable=True))
    op.add_column("materials", sa.Column("stock_length_unit", sa.String(2), nullable=True))
    op.create_check_constraint(
        op.f("ck_materials_stock_length_unit"), "materials", "stock_length_unit IN ('ft', 'm')"
    )
    op.create_check_constraint(
        op.f("ck_materials_bar_stock_length"),
        "materials",
        "(unit = 'bar') = (stock_length IS NOT NULL AND stock_length > 0"
        " AND stock_length_unit IS NOT NULL)",
    )

    op.add_column(
        "products",
        sa.Column("pricing_method", sa.String(20), server_default="computed", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_products_pricing_method"), "products", "pricing_method IN ('per_sqft', 'computed')"
    )
    for table in ("products", "product_options"):
        op.add_column(
            table,
            sa.Column("rate_per_sqft", sa.Numeric(12, 2), server_default="0", nullable=False),
        )
        op.create_check_constraint(
            op.f(f"ck_{table}_rate_per_sqft_nonnegative"), table, "rate_per_sqft >= 0"
        )


def downgrade() -> None:
    for table in ("product_options", "products"):
        op.drop_constraint(op.f(f"ck_{table}_rate_per_sqft_nonnegative"), table, type_="check")
        op.drop_column(table, "rate_per_sqft")
    op.drop_constraint(op.f("ck_products_pricing_method"), "products", type_="check")
    op.drop_column("products", "pricing_method")

    op.drop_constraint(op.f("ck_materials_bar_stock_length"), "materials", type_="check")
    op.drop_constraint(op.f("ck_materials_stock_length_unit"), "materials", type_="check")
    op.drop_column("materials", "stock_length_unit")
    op.drop_column("materials", "stock_length")

    for table, price in PRICE.items():
        op.drop_constraint(op.f(f"ck_{table}_unit"), table, type_="check")
        op.execute(
            f"UPDATE {table} SET unit = 'sqm', {price} = ROUND({price} * {SQFT_PER_SQM}, 2)"  # noqa: S608 - constants
            " WHERE unit = 'sqft'"
        )
        op.execute(
            f"UPDATE {table} SET unit = 'lm', {price} = ROUND({price} / {FT_IN_M}, 2)"  # noqa: S608 - constants
            " WHERE unit = 'ft'"
        )
        # No old equivalent: kilos and whole bars become "per piece" (lossy).
        op.execute(f"UPDATE {table} SET unit = 'piece' WHERE unit IN ('kg', 'bar')")  # noqa: S608
        op.create_check_constraint(op.f(f"ck_{table}_unit"), table, f"unit IN {OLD_UNITS}")
