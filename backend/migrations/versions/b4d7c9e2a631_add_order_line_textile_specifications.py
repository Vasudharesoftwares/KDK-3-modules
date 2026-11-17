"""add customer-specific textile specifications to order lines

Revision ID: b4d7c9e2a631
Revises: 7a31c9e4b6f2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4d7c9e2a631"
down_revision: Union[str, Sequence[str], None] = "7a31c9e4b6f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_order_lines", sa.Column("material", sa.String(length=120), nullable=True))
    op.add_column("sales_order_lines", sa.Column("fibre_content", sa.String(length=200), nullable=True))
    op.add_column("sales_order_lines", sa.Column("yarn_count", sa.String(length=60), nullable=True))
    op.add_column("sales_order_lines", sa.Column("ply", sa.String(length=30), nullable=True))
    op.add_column("sales_order_lines", sa.Column("yarn_type", sa.String(length=80), nullable=True))
    op.add_column("sales_order_lines", sa.Column("colour", sa.String(length=100), nullable=True))
    op.add_column("sales_order_lines", sa.Column("shade_code", sa.String(length=60), nullable=True))
    op.add_column("sales_order_lines", sa.Column("pattern", sa.String(length=120), nullable=True))
    op.add_column("sales_order_lines", sa.Column("fabric_construction", sa.String(length=120), nullable=True))
    op.add_column("sales_order_lines", sa.Column("weave_type", sa.String(length=120), nullable=True))
    op.add_column("sales_order_lines", sa.Column("width_mm", sa.Numeric(12, 3), nullable=True))
    op.add_column("sales_order_lines", sa.Column("size_specification", sa.String(length=120), nullable=True))
    op.add_column("sales_order_lines", sa.Column("gsm", sa.Numeric(10, 3), nullable=True))
    op.add_column("sales_order_lines", sa.Column("quality_grade", sa.String(length=60), nullable=True))
    op.add_column("sales_order_lines", sa.Column("finish", sa.String(length=100), nullable=True))

    op.create_check_constraint(
        "ck_order_line_width_positive",
        "sales_order_lines",
        "width_mm IS NULL OR width_mm > 0",
    )
    op.create_check_constraint(
        "ck_order_line_gsm_positive",
        "sales_order_lines",
        "gsm IS NULL OR gsm > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_order_line_gsm_positive", "sales_order_lines", type_="check")
    op.drop_constraint("ck_order_line_width_positive", "sales_order_lines", type_="check")

    for column in (
        "finish", "quality_grade", "gsm", "size_specification", "width_mm",
        "weave_type", "fabric_construction", "pattern", "shade_code",
        "colour", "yarn_type", "ply", "yarn_count", "fibre_content", "material",
    ):
        op.drop_column("sales_order_lines", column)
