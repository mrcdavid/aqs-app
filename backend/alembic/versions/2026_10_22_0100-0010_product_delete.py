"""staff can delete products: products.deleted_at / deleted_by, codes unique among live products

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22 01:00:00

Written by hand. A product that was never quoted is removed for real; one that was quoted is only
marked deleted (its quotations still point at it), so its code must become reusable: the unique
constraint on `code` becomes a unique index over products that aren't deleted.
Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("deleted_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_products_deleted_by_users"), "products", "users", ["deleted_by"], ["id"]
    )
    op.drop_constraint(op.f("uq_products_code"), "products", type_="unique")
    op.create_index(
        "uq_products_code_live",
        "products",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Deleted products come back as archived ones. Their code may now be used again by a live
    # product, so give them a unique one first ("SW-STD" -> "SW-STD~1a2b3c4d", max 30 chars).
    op.execute(
        "UPDATE products SET code = left(code, 21) || '~' || left(id::text, 8), is_active = false"
        " WHERE deleted_at IS NOT NULL"
    )
    op.drop_index("uq_products_code_live", table_name="products")
    op.create_unique_constraint(op.f("uq_products_code"), "products", ["code"])
    op.drop_constraint(op.f("fk_products_deleted_by_users"), "products", type_="foreignkey")
    op.drop_column("products", "deleted_by")
    op.drop_column("products", "deleted_at")
