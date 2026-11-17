"""Add direct purchase entries.

Revision ID: b7c1d9e2f604
Revises: 5a96477304da
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c1d9e2f604"
down_revision: Union[str, Sequence[str], None] = "5a96477304da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("purchase_number", sa.String(60), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("supplier_name", sa.String(200), nullable=False),
        sa.Column("mobile", sa.String(30)),
        sa.Column("gstin", sa.String(20)),
        sa.Column("supplier_bill_number", sa.String(100)),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id")),
        sa.Column("freight", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("other_charges", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(30), nullable=False, server_default="unpaid"),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("remarks", sa.Text()),
        sa.Column("subtotal", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "purchase_number", name="uq_purchase_entries_number"),
    )
    op.create_index(
        "ix_purchase_entries_company_date",
        "purchase_entries",
        ["company_id", "purchase_date"],
    )

    op.create_table(
        "purchase_entry_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_entry_id", sa.Integer(),
                  sa.ForeignKey("purchase_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("material_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("quantity", sa.Numeric(16, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("rate", sa.Numeric(16, 4), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_entry_line_qty"),
        sa.CheckConstraint("rate >= 0", name="ck_purchase_entry_line_rate"),
        sa.UniqueConstraint("purchase_entry_id", "line_number",
                            name="uq_purchase_entry_line_number"),
    )


def downgrade() -> None:
    op.drop_table("purchase_entry_lines")
    op.drop_index("ix_purchase_entries_company_date", table_name="purchase_entries")
    op.drop_table("purchase_entries")
