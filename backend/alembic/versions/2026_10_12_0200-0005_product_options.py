"""optional product add-ons: product_options, product_components.option_id

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12 02:00:00

Written by hand. Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_options")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_options_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("product_id", "name", name=op.f("uq_product_options_product_id")),
    )
    op.create_index(op.f("ix_product_options_product_id"), "product_options", ["product_id"])

    op.add_column("product_components", sa.Column("option_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_product_components_option_id_product_options"),
        "product_components",
        "product_options",
        ["option_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_product_components_option_id"), "product_components", ["option_id"])


def downgrade() -> None:
    # Add-on lines would otherwise silently become always-included lines.
    op.execute("DELETE FROM product_components WHERE option_id IS NOT NULL")
    op.drop_index(op.f("ix_product_components_option_id"), table_name="product_components")
    op.drop_constraint(
        op.f("fk_product_components_option_id_product_options"),
        "product_components",
        type_="foreignkey",
    )
    op.drop_column("product_components", "option_id")
    op.drop_index(op.f("ix_product_options_product_id"), table_name="product_options")
    op.drop_table("product_options")
