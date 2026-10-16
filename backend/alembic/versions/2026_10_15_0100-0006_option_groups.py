"""choose-one option groups (e.g. glass type) and size reductions on options (e.g. open back)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-15 01:00:00

Written by hand. Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_option_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_option_groups")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_option_groups_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("product_id", "name", name=op.f("uq_product_option_groups_product_id")),
    )
    op.create_index(
        op.f("ix_product_option_groups_product_id"), "product_option_groups", ["product_id"]
    )

    op.add_column("product_options", sa.Column("group_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_product_options_group_id_product_option_groups"),
        "product_options",
        "product_option_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_product_options_group_id"), "product_options", ["group_id"])
    for column in ("width_reduction_mm", "height_reduction_mm"):
        op.add_column(
            "product_options",
            sa.Column(column, sa.Integer(), server_default="0", nullable=False),
        )
    op.create_check_constraint(
        op.f("ck_product_options_reduction_range"),
        "product_options",
        "width_reduction_mm BETWEEN 0 AND 2000 AND height_reduction_mm BETWEEN 0 AND 2000",
    )
    # Names are unique per group now (two groups may both have a "None" choice).
    op.drop_constraint(op.f("uq_product_options_product_id"), "product_options", type_="unique")
    op.create_unique_constraint(
        op.f("uq_product_options_product_id"), "product_options", ["product_id", "group_id", "name"]
    )


def downgrade() -> None:
    # Choices only make sense inside their group; their lines go with them.
    op.execute("DELETE FROM product_options WHERE group_id IS NOT NULL")
    op.drop_constraint(op.f("uq_product_options_product_id"), "product_options", type_="unique")
    op.create_unique_constraint(
        op.f("uq_product_options_product_id"), "product_options", ["product_id", "name"]
    )
    op.drop_constraint(op.f("ck_product_options_reduction_range"), "product_options", type_="check")
    op.drop_column("product_options", "height_reduction_mm")
    op.drop_column("product_options", "width_reduction_mm")
    op.drop_index(op.f("ix_product_options_group_id"), table_name="product_options")
    op.drop_constraint(
        op.f("fk_product_options_group_id_product_option_groups"),
        "product_options",
        type_="foreignkey",
    )
    op.drop_column("product_options", "group_id")
    op.drop_index(op.f("ix_product_option_groups_product_id"), table_name="product_option_groups")
    op.drop_table("product_option_groups")
