"""several products per quotation: quotation_items

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-16 01:00:00

Written by hand. Every existing quotation becomes a one-item quotation: its product, size,
quantity and frozen prices move into quotation_items; the quotation keeps the client, status,
number and total. Verified with `alembic check`.
"""

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ITEM_KEYS = ("product", "input", "pricing", "choices", "options")


def _json(value: Any) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else value


def upgrade() -> None:
    op.create_table(
        "quotation_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("quotation_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("product_name", sa.String(120), nullable=False),
        sa.Column("input_width", sa.Numeric(8, 2), nullable=False),
        sa.Column("input_height", sa.Numeric(8, 2), nullable=False),
        sa.Column("input_unit", sa.String(2), nullable=False),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_items")),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_items_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_quotation_items_product_id_products")
        ),
        sa.UniqueConstraint(
            "quotation_id", "position", name=op.f("uq_quotation_items_quotation_id")
        ),
        sa.CheckConstraint(
            "input_unit IN ('cm', 'in')", name=op.f("ck_quotation_items_input_unit")
        ),
        sa.CheckConstraint(
            "quantity BETWEEN 1 AND 100", name=op.f("ck_quotation_items_quantity_range")
        ),
        sa.CheckConstraint(
            "width_mm > 0 AND height_mm > 0", name=op.f("ck_quotation_items_size_positive")
        ),
    )
    op.create_index(op.f("ix_quotation_items_quotation_id"), "quotation_items", ["quotation_id"])
    op.create_index(op.f("ix_quotation_items_product_id"), "quotation_items", ["product_id"])

    # ---- move each quotation's single product into its first item ----
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, product_id, input_width, input_height, input_unit, width_mm, height_mm,"
            " quantity, total, snapshot FROM quotations"
        )
    ).mappings()
    insert_item = sa.text(
        "INSERT INTO quotation_items (id, quotation_id, position, product_id, product_name,"
        " input_width, input_height, input_unit, width_mm, height_mm, quantity, amount, snapshot)"
        " VALUES (gen_random_uuid(), :quotation_id, 0, :product_id, :product_name, :input_width,"
        " :input_height, :input_unit, :width_mm, :height_mm, :quantity, :amount, :snapshot)"
    ).bindparams(sa.bindparam("snapshot", type_=postgresql.JSONB))
    update_quote = sa.text("UPDATE quotations SET snapshot = :snapshot WHERE id = :id").bindparams(
        sa.bindparam("snapshot", type_=postgresql.JSONB)
    )
    for row in list(rows):
        snap = _json(row["snapshot"])
        pricing = snap["pricing"]
        item = {key: snap.get(key, []) for key in ITEM_KEYS}
        conn.execute(
            insert_item,
            {
                "quotation_id": row["id"],
                "product_id": row["product_id"],
                "product_name": snap["product"]["name"],
                "input_width": row["input_width"],
                "input_height": row["input_height"],
                "input_unit": row["input_unit"],
                "width_mm": row["width_mm"],
                "height_mm": row["height_mm"],
                "quantity": row["quantity"],
                # The calculated (rounded) price; an amount changed on approval stays in `total`.
                "amount": Decimal(pricing.get("rounded_total", pricing["total"])),
                "snapshot": item,
            },
        )
        rest = {k: v for k, v in snap.items() if k not in ITEM_KEYS}
        conn.execute(update_quote, {"id": row["id"], "snapshot": {**rest, "version": 5}})

    for name in ("input_unit", "quantity_range", "size_positive"):
        op.drop_constraint(op.f(f"ck_quotations_{name}"), "quotations", type_="check")
    op.drop_index(op.f("ix_quotations_product_id"), table_name="quotations")
    op.drop_constraint(op.f("fk_quotations_product_id_products"), "quotations", type_="foreignkey")
    for column in (
        "product_id",
        "input_width",
        "input_height",
        "input_unit",
        "width_mm",
        "height_mm",
        "quantity",
    ):
        op.drop_column("quotations", column)


def downgrade() -> None:
    # Back to one product per quotation: the first item is kept, any others are dropped.
    op.add_column("quotations", sa.Column("product_id", sa.Uuid(), nullable=True))
    op.add_column("quotations", sa.Column("input_width", sa.Numeric(8, 2), nullable=True))
    op.add_column("quotations", sa.Column("input_height", sa.Numeric(8, 2), nullable=True))
    op.add_column("quotations", sa.Column("input_unit", sa.String(2), nullable=True))
    op.add_column("quotations", sa.Column("width_mm", sa.Integer(), nullable=True))
    op.add_column("quotations", sa.Column("height_mm", sa.Integer(), nullable=True))
    op.add_column("quotations", sa.Column("quantity", sa.Integer(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT q.id, q.snapshot AS q_snapshot, i.product_id, i.input_width, i.input_height,"
            " i.input_unit, i.width_mm, i.height_mm, i.quantity, i.snapshot AS i_snapshot"
            " FROM quotations q JOIN quotation_items i ON i.quotation_id = q.id AND i.position = 0"
        )
    ).mappings()
    update_quote = sa.text(
        "UPDATE quotations SET product_id = :product_id, input_width = :input_width,"
        " input_height = :input_height, input_unit = :input_unit, width_mm = :width_mm,"
        " height_mm = :height_mm, quantity = :quantity, snapshot = :snapshot WHERE id = :id"
    ).bindparams(sa.bindparam("snapshot", type_=postgresql.JSONB))
    for row in list(rows):
        snapshot = {**_json(row["q_snapshot"]), **_json(row["i_snapshot"]), "version": 4}
        conn.execute(
            update_quote,
            {
                "id": row["id"],
                "product_id": row["product_id"],
                "input_width": row["input_width"],
                "input_height": row["input_height"],
                "input_unit": row["input_unit"],
                "width_mm": row["width_mm"],
                "height_mm": row["height_mm"],
                "quantity": row["quantity"],
                "snapshot": snapshot,
            },
        )
    op.execute("DELETE FROM quotations WHERE product_id IS NULL")  # had no items at all

    for column in (
        "product_id",
        "input_width",
        "input_height",
        "input_unit",
        "width_mm",
        "height_mm",
        "quantity",
    ):
        op.alter_column("quotations", column, nullable=False)
    op.create_foreign_key(
        op.f("fk_quotations_product_id_products"), "quotations", "products", ["product_id"], ["id"]
    )
    op.create_index(op.f("ix_quotations_product_id"), "quotations", ["product_id"])
    op.create_check_constraint(
        op.f("ck_quotations_input_unit"), "quotations", "input_unit IN ('cm', 'in')"
    )
    op.create_check_constraint(
        op.f("ck_quotations_quantity_range"), "quotations", "quantity BETWEEN 1 AND 100"
    )
    op.create_check_constraint(
        op.f("ck_quotations_size_positive"), "quotations", "width_mm > 0 AND height_mm > 0"
    )
    op.drop_index(op.f("ix_quotation_items_product_id"), table_name="quotation_items")
    op.drop_index(op.f("ix_quotation_items_quotation_id"), table_name="quotation_items")
    op.drop_table("quotation_items")
