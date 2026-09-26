"""quotations, quote_counters, and quotation settings on pricing_settings

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26 01:46:00

Written by hand (autogenerate skips CHECK constraints on existing tables and duplicates enum
CHECKs). Verified with `alembic check`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TERMS = (
    "1. Prices are valid until the date shown above.\n"
    "2. Final price is subject to on-site measurement.\n"
    "(Edit these terms in Admin > Settings.)"
)


def upgrade() -> None:
    # ---- settings used on quotations and PDFs ----
    op.add_column(
        "pricing_settings",
        sa.Column("quote_validity_days", sa.Integer(), server_default="30", nullable=False),
    )
    op.add_column(
        "pricing_settings",
        sa.Column("business_name", sa.String(120), server_default="", nullable=False),
    )
    op.add_column(
        "pricing_settings",
        sa.Column("business_address", sa.String(300), server_default="", nullable=False),
    )
    op.add_column(
        "pricing_settings",
        sa.Column("business_contact", sa.String(120), server_default="", nullable=False),
    )
    op.add_column(
        "pricing_settings",
        sa.Column("quote_terms", sa.Text(), server_default="", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_pricing_settings_validity_range"),
        "pricing_settings",
        "quote_validity_days BETWEEN 1 AND 365",
    )
    # Clearly-marked placeholders until the owner fills in real details.
    op.execute(
        sa.text(
            "UPDATE pricing_settings SET business_name = :name, business_address = :address,"
            " quote_terms = :terms WHERE id = 1"
        ).bindparams(
            name="Your Business Name",
            address="Set your address in Admin > Settings",
            terms=DEFAULT_TERMS,
        )
    )

    # ---- quotations ----
    op.create_table(
        "quotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("number", sa.String(20), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_width", sa.Numeric(8, 2), nullable=False),
        sa.Column("input_height", sa.Numeric(8, 2), nullable=False),
        sa.Column("input_unit", sa.String(2), nullable=False),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("customer_city", sa.String(80), nullable=False),
        sa.Column("customer_province", sa.String(80), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("pdf_file", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotations")),
        sa.UniqueConstraint("number", name=op.f("uq_quotations_number")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_quotations_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_quotations_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], name=op.f("fk_quotations_reviewed_by_users")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_quotations_status"),
        ),
        sa.CheckConstraint(
            "status <> 'approved' OR (number IS NOT NULL AND reviewed_at IS NOT NULL"
            " AND valid_until IS NOT NULL)",
            name=op.f("ck_quotations_approved_fields"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR (reviewed_at IS NOT NULL AND review_note IS NOT NULL)",
            name=op.f("ck_quotations_rejected_fields"),
        ),
        sa.CheckConstraint("input_unit IN ('cm', 'in')", name=op.f("ck_quotations_input_unit")),
        sa.CheckConstraint("quantity BETWEEN 1 AND 100", name=op.f("ck_quotations_quantity_range")),
        sa.CheckConstraint(
            "width_mm > 0 AND height_mm > 0", name=op.f("ck_quotations_size_positive")
        ),
    )
    op.create_index("ix_quotations_created_at", "quotations", ["created_at"])
    op.create_index(op.f("ix_quotations_user_id"), "quotations", ["user_id"])
    op.create_index(op.f("ix_quotations_product_id"), "quotations", ["product_id"])
    op.create_index(op.f("ix_quotations_status"), "quotations", ["status"])

    op.create_table(
        "quote_counters",
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("year", name=op.f("pk_quote_counters")),
    )


def downgrade() -> None:
    op.drop_table("quote_counters")
    op.drop_table("quotations")
    op.drop_constraint(
        op.f("ck_pricing_settings_validity_range"), "pricing_settings", type_="check"
    )
    for column in (
        "quote_terms",
        "business_contact",
        "business_address",
        "business_name",
        "quote_validity_days",
    ):
        op.drop_column("pricing_settings", column)
