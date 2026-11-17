"""allow production quantity to exceed ordered quantity

Revision ID: 7a31c9e4b6f2
Revises: 59258e402cc0
"""
from typing import Sequence, Union

from alembic import op

revision: str = "7a31c9e4b6f2"
down_revision: Union[str, Sequence[str], None] = "59258e402cc0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_order_line_produced_lte_ordered",
        "sales_order_lines",
        type_="check",
    )


def downgrade() -> None:
    # Downgrade is intentionally guarded: it can fail if any line contains
    # legitimate overproduction. Correct the data before downgrading.
    op.create_check_constraint(
        "ck_order_line_produced_lte_ordered",
        "sales_order_lines",
        "produced_qty <= ordered_qty",
    )
