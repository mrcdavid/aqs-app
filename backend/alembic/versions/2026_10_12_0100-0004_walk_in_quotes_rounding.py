"""staff quotations for walk-in clients, total rounding step, owner name for signatures

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12 01:00:00

Written by hand. Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- settings: round totals up (default to the next 100) and the owner who signs ----
    op.add_column(
        "pricing_settings",
        sa.Column("rounding_step", sa.Numeric(12, 2), server_default="100", nullable=False),
    )
    op.add_column(
        "pricing_settings",
        sa.Column("owner_name", sa.String(120), server_default="", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_pricing_settings_rounding_step_range"),
        "pricing_settings",
        "rounding_step >= 0 AND rounding_step <= 100000",
    )
    op.execute(
        sa.text("UPDATE pricing_settings SET owner_name = :name WHERE id = 1").bindparams(
            name="Cleo David"
        )
    )

    # ---- quotations: walk-in clients have no account; record who created each request ----
    op.add_column("quotations", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.execute("UPDATE quotations SET created_by = user_id")
    op.alter_column("quotations", "created_by", nullable=False)
    op.create_foreign_key(
        op.f("fk_quotations_created_by_users"), "quotations", "users", ["created_by"], ["id"]
    )
    op.alter_column("quotations", "user_id", nullable=True)


def downgrade() -> None:
    # Walk-in quotations are kept, owned by the staff member who created them.
    op.execute("UPDATE quotations SET user_id = created_by WHERE user_id IS NULL")
    op.alter_column("quotations", "user_id", nullable=False)
    op.drop_constraint(op.f("fk_quotations_created_by_users"), "quotations", type_="foreignkey")
    op.drop_column("quotations", "created_by")

    op.drop_constraint(
        op.f("ck_pricing_settings_rounding_step_range"), "pricing_settings", type_="check"
    )
    op.drop_column("pricing_settings", "owner_name")
    op.drop_column("pricing_settings", "rounding_step")
