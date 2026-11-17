"""Add current customer-requested order item attributes."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3b8c1d9a620"
down_revision: Union[str, Sequence[str], None] = "e1a9c7d4b620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_order_lines",
        sa.Column("brand", sa.String(120), nullable=True),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column("occasion", sa.String(120), nullable=True),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column("pure", sa.String(120), nullable=True),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column("weight", sa.String(80), nullable=True),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column("washcare", sa.Text(), nullable=True),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column(
            "custom_attributes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column(
        "sales_order_lines",
        "custom_attributes",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("sales_order_lines", "custom_attributes")
    op.drop_column("sales_order_lines", "washcare")
    op.drop_column("sales_order_lines", "weight")
    op.drop_column("sales_order_lines", "pure")
    op.drop_column("sales_order_lines", "occasion")
    op.drop_column("sales_order_lines", "brand")
