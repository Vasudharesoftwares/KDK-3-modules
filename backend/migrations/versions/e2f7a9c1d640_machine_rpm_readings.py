"""Add machine RPM readings.

Revision ID: e2f7a9c1d640
Revises: d7e4a91c6b20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2f7a9c1d640"
down_revision: Union[str, Sequence[str], None] = "d7e4a91c6b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "machine_rpm_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(),
                  sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("machine_id", sa.Integer(),
                  sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_rpm", sa.Numeric(10, 2), nullable=False),
        sa.Column("standard_rpm", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "actual_rpm > 0",
            name="ck_machine_rpm_reading_actual_positive",
        ),
        sa.CheckConstraint(
            "standard_rpm > 0",
            name="ck_machine_rpm_reading_standard_positive",
        ),
    )
    op.create_index(
        "ix_machine_rpm_readings_company_machine_time",
        "machine_rpm_readings",
        ["company_id", "machine_id", "recorded_at"],
    )
    op.create_index(
        "ix_machine_rpm_readings_company_time",
        "machine_rpm_readings",
        ["company_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_machine_rpm_readings_company_time",
        table_name="machine_rpm_readings",
    )
    op.drop_index(
        "ix_machine_rpm_readings_company_machine_time",
        table_name="machine_rpm_readings",
    )
    op.drop_table("machine_rpm_readings")
