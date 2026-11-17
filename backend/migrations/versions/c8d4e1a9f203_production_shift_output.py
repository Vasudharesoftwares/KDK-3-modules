"""Add simple machine-wise shift production output records.

Revision ID: c8d4e1a9f203
Revises: b7c1d9e2f604
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8d4e1a9f203"
down_revision: Union[str, Sequence[str], None] = "b7c1d9e2f604"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_shift_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(),
                  sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("machine_id", sa.Integer(),
                  sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("shift_id", sa.Integer(),
                  sa.ForeignKey("shifts.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("unit_code", sa.String(20), nullable=False),
        sa.Column("target_output", sa.Numeric(16, 3), nullable=False),
        sa.Column("actual_output", sa.Numeric(16, 3), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "unit_code IN ('metres', 'pieces')",
            name="ck_production_shift_entry_unit",
        ),
        sa.CheckConstraint(
            "target_output > 0",
            name="ck_production_shift_entry_target_positive",
        ),
        sa.CheckConstraint(
            "actual_output >= 0",
            name="ck_production_shift_entry_actual_nonnegative",
        ),
    )
    op.create_index(
        "ix_production_shift_entries_company_date",
        "production_shift_entries",
        ["company_id", "work_date"],
    )
    op.create_index(
        "ix_production_shift_entries_machine_date",
        "production_shift_entries",
        ["machine_id", "work_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_production_shift_entries_machine_date",
        table_name="production_shift_entries",
    )
    op.drop_index(
        "ix_production_shift_entries_company_date",
        table_name="production_shift_entries",
    )
    op.drop_table("production_shift_entries")
