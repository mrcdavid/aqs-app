"""super admins can delete quotations (soft delete): quotations.deleted_at / deleted_by

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-16 02:00:00

Written by hand. Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quotations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("quotations", sa.Column("deleted_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_quotations_deleted_by_users"), "quotations", "users", ["deleted_by"], ["id"]
    )


def downgrade() -> None:
    # Deleted quotations would otherwise come back; remove them for real (items cascade).
    op.execute("DELETE FROM quotations WHERE deleted_at IS NOT NULL")
    op.drop_constraint(op.f("fk_quotations_deleted_by_users"), "quotations", type_="foreignkey")
    op.drop_column("quotations", "deleted_by")
    op.drop_column("quotations", "deleted_at")
