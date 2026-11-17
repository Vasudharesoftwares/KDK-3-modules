from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductionPlan(Base):
    __tablename__ = "production_plans"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "plan_number",
            name="uq_production_plans_company_number",
        ),
        CheckConstraint(
            "planned_qty > 0",
            name="ck_production_plans_planned_positive",
        ),
        CheckConstraint(
            "actual_qty >= 0",
            name="ck_production_plans_actual_nonnegative",
        ),
        CheckConstraint(
            "status IN ('draft','scheduled','in_progress','completed','cancelled')",
            name="ck_production_plans_status",
        ),
        Index(
            "ix_production_plans_company_status",
            "company_id", "status",
        ),
        Index(
            "ix_production_plans_order_line",
            "sales_order_line_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"), nullable=False
    )
    sales_order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id"), nullable=False
    )
    sales_order_line_id: Mapped[int] = mapped_column(
        ForeignKey("sales_order_lines.id"), nullable=False
    )

    plan_number: Mapped[str] = mapped_column(String(60), nullable=False)
    planned_qty: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), nullable=False
    )
    actual_qty: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), default=0, nullable=False
    )
    uom_code: Mapped[str] = mapped_column(String(20), nullable=False)

    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class PlanningMachine(Base):
    __tablename__ = "planning_machines"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "branch_id", "normalized_name",
            name="uq_planning_machines_scope_name",
        ),
        Index(
            "ix_planning_machines_scope_active",
            "company_id", "branch_id", "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class PlanningWorker(Base):
    __tablename__ = "planning_workers"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "branch_id", "normalized_name",
            name="uq_planning_workers_scope_name",
        ),
        Index(
            "ix_planning_workers_scope_active",
            "company_id", "branch_id", "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class PlanningAllocation(Base):
    __tablename__ = "planning_allocations"
    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_planning_allocations_positive_interval",
        ),
        Index(
            "ix_planning_allocations_machine_interval",
            "machine_id", "starts_at", "ends_at",
        ),
        Index(
            "ix_planning_allocations_worker_interval",
            "worker_id", "starts_at", "ends_at",
        ),
        Index(
            "ix_planning_allocations_plan",
            "plan_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("production_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machines.id"))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"))
    worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("workers.id")
    )
    planning_machine_id: Mapped[int | None] = mapped_column(
        ForeignKey("planning_machines.id")
    )
    planning_worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("planning_workers.id")
    )
    machine_name_snapshot: Mapped[str | None] = mapped_column(String(120))
    worker_name_snapshot: Mapped[str | None] = mapped_column(String(120))
    manual_entry: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )

    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlanningEvent(Base):
    __tablename__ = "planning_events"
    __table_args__ = (
        Index(
            "ix_planning_events_plan_time",
            "plan_id", "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("production_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
