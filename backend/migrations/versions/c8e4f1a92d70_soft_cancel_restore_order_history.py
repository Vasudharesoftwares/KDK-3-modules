"""add recoverable order cancellation and status history

Revision ID: c8e4f1a92d70
Revises: b4d7c9e2a631
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8e4f1a92d70"
down_revision: Union[str, Sequence[str], None] = "b4d7c9e2a631"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_orders",
        sa.Column("cancelled_from_status", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "order_status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("sales_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("quantity_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('cancelled','restored')",
            name="ck_order_status_events_action",
        ),
    )
    op.create_index(
        "ix_order_status_events_order_time",
        "order_status_events",
        ["order_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_status_events_order_time",
        table_name="order_status_events",
    )
    op.drop_table("order_status_events")
    op.drop_column("sales_orders", "cancelled_at")
    op.drop_column("sales_orders", "cancellation_reason")
    op.drop_column("sales_orders", "cancelled_from_status")
