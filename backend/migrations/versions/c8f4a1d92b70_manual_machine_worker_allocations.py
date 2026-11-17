"""Add reusable manual machine and worker allocations."""

from alembic import op
import sqlalchemy as sa

revision = "c8f4a1d92b70"
down_revision = "a7d2c9e5f104"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "planning_machines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id", "branch_id", "normalized_name",
            name="uq_planning_machines_scope_name",
        ),
    )
    op.create_index(
        "ix_planning_machines_scope_active",
        "planning_machines", ["company_id", "branch_id", "is_active"],
    )

    op.create_table(
        "planning_workers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id", "branch_id", "normalized_name",
            name="uq_planning_workers_scope_name",
        ),
    )
    op.create_index(
        "ix_planning_workers_scope_active",
        "planning_workers", ["company_id", "branch_id", "is_active"],
    )

    op.alter_column("planning_allocations", "machine_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("planning_allocations", "shift_id", existing_type=sa.Integer(), nullable=True)

    op.add_column(
        "planning_allocations",
        sa.Column("planning_machine_id", sa.Integer(), sa.ForeignKey("planning_machines.id"), nullable=True),
    )
    op.add_column(
        "planning_allocations",
        sa.Column("planning_worker_id", sa.Integer(), sa.ForeignKey("planning_workers.id"), nullable=True),
    )
    op.add_column(
        "planning_allocations",
        sa.Column("machine_name_snapshot", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "planning_allocations",
        sa.Column("worker_name_snapshot", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "planning_allocations",
        sa.Column("manual_entry", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade():
    op.drop_column("planning_allocations", "manual_entry")
    op.drop_column("planning_allocations", "worker_name_snapshot")
    op.drop_column("planning_allocations", "machine_name_snapshot")
    op.drop_column("planning_allocations", "planning_worker_id")
    op.drop_column("planning_allocations", "planning_machine_id")

    op.alter_column("planning_allocations", "shift_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("planning_allocations", "machine_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_planning_workers_scope_active", table_name="planning_workers")
    op.drop_table("planning_workers")
    op.drop_index("ix_planning_machines_scope_active", table_name="planning_machines")
    op.drop_table("planning_machines")
