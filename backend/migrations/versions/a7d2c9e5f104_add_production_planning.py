"""Add production planning, machine allocations and planning audit events."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7d2c9e5f104"
down_revision: Union[str, Sequence[str], None] = "f3b8c1d9a620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id", sa.Integer(),
            sa.ForeignKey("companies.id"), nullable=False,
        ),
        sa.Column(
            "branch_id", sa.Integer(),
            sa.ForeignKey("branches.id"), nullable=False,
        ),
        sa.Column(
            "sales_order_id", sa.Integer(),
            sa.ForeignKey("sales_orders.id"), nullable=False,
        ),
        sa.Column(
            "sales_order_line_id", sa.Integer(),
            sa.ForeignKey("sales_order_lines.id"), nullable=False,
        ),
        sa.Column("plan_number", sa.String(60), nullable=False),
        sa.Column("planned_qty", sa.Numeric(16, 3), nullable=False),
        sa.Column(
            "actual_qty", sa.Numeric(16, 3),
            server_default="0", nullable=False,
        ),
        sa.Column("uom_code", sa.String(20), nullable=False),
        sa.Column("planned_start_date", sa.Date(), nullable=False),
        sa.Column("target_end_date", sa.Date(), nullable=True),
        sa.Column(
            "status", sa.String(30),
            server_default="draft", nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "company_id", "plan_number",
            name="uq_production_plans_company_number",
        ),
        sa.CheckConstraint(
            "planned_qty > 0",
            name="ck_production_plans_planned_positive",
        ),
        sa.CheckConstraint(
            "actual_qty >= 0",
            name="ck_production_plans_actual_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('draft','scheduled','in_progress','completed','cancelled')",
            name="ck_production_plans_status",
        ),
    )

    op.create_index(
        "ix_production_plans_company_status",
        "production_plans", ["company_id", "status"],
    )
    op.create_index(
        "ix_production_plans_order_line",
        "production_plans", ["sales_order_line_id"],
    )

    op.create_table(
        "planning_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id", sa.Integer(),
            sa.ForeignKey("production_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "machine_id", sa.Integer(),
            sa.ForeignKey("machines.id"), nullable=False,
        ),
        sa.Column(
            "shift_id", sa.Integer(),
            sa.ForeignKey("shifts.id"), nullable=False,
        ),
        sa.Column(
            "worker_id", sa.Integer(),
            sa.ForeignKey("workers.id"), nullable=True,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "ends_at > starts_at",
            name="ck_planning_allocations_positive_interval",
        ),
    )

    op.create_index(
        "ix_planning_allocations_machine_interval",
        "planning_allocations", ["machine_id", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_planning_allocations_worker_interval",
        "planning_allocations", ["worker_id", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_planning_allocations_plan",
        "planning_allocations", ["plan_id"],
    )

    op.create_table(
        "planning_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id", sa.Integer(),
            sa.ForeignKey("production_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    op.create_index(
        "ix_planning_events_plan_time",
        "planning_events", ["plan_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_planning_events_plan_time", table_name="planning_events")
    op.drop_table("planning_events")

    op.drop_index("ix_planning_allocations_plan", table_name="planning_allocations")
    op.drop_index(
        "ix_planning_allocations_worker_interval",
        table_name="planning_allocations",
    )
    op.drop_index(
        "ix_planning_allocations_machine_interval",
        table_name="planning_allocations",
    )
    op.drop_table("planning_allocations")

    op.drop_index(
        "ix_production_plans_order_line",
        table_name="production_plans",
    )
    op.drop_index(
        "ix_production_plans_company_status",
        table_name="production_plans",
    )
    op.drop_table("production_plans")
