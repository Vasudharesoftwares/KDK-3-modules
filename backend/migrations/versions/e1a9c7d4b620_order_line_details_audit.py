"""audit customer order item specification edits

Revision ID: e1a9c7d4b620
Revises: c8e4f1a92d70
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a9c7d4b620"
down_revision: Union[str, Sequence[str], None] = "c8e4f1a92d70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_line_details_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("sales_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "line_id",
            sa.Integer(),
            sa.ForeignKey("sales_order_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_order_line_details_events_order_line_time",
        "order_line_details_events",
        ["order_id", "line_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_line_details_events_order_line_time",
        table_name="order_line_details_events",
    )
    op.drop_table("order_line_details_events")
