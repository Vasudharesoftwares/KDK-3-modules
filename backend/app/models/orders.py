from sqlalchemy import JSON
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index,
    Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "order_number", name="uq_sales_orders_company_number"),
        CheckConstraint(
            "priority IN ('low','normal','high','urgent')",
            name="ck_sales_orders_priority"
        ),
        CheckConstraint(
            "status IN ('draft','confirmed','in_production','completed','cancelled')",
            name="ck_sales_orders_status"
        ),
        Index("ix_sales_orders_company_date", "company_id", "order_date"),
        Index("ix_sales_orders_company_customer", "company_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(60), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    cancelled_from_status: Mapped[str | None] = mapped_column(String(30))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
        order_by="SalesOrderLine.line_number"
    )


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "line_number", name="uq_sales_order_lines_number"),
        CheckConstraint("ordered_qty > 0", name="ck_order_line_ordered_positive"),
        CheckConstraint("produced_qty >= 0", name="ck_order_line_produced_nonnegative"),
        CheckConstraint("approved_qty >= 0", name="ck_order_line_approved_nonnegative"),
        CheckConstraint("dispatched_qty >= 0", name="ck_order_line_dispatched_nonnegative"),
        CheckConstraint("approved_qty <= produced_qty", name="ck_order_line_approved_lte_produced"),
        CheckConstraint("dispatched_qty <= approved_qty", name="ck_order_line_dispatched_lte_approved"),
        CheckConstraint("width_mm IS NULL OR width_mm > 0", name="ck_order_line_width_positive"),
        CheckConstraint("gsm IS NULL OR gsm > 0", name="ck_order_line_gsm_positive"),
        Index("ix_sales_order_lines_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    design_code: Mapped[str | None] = mapped_column(String(80))

    # Customer-requested specifications for this order item.
    material: Mapped[str | None] = mapped_column(String(120))
    fibre_content: Mapped[str | None] = mapped_column(String(200))
    yarn_count: Mapped[str | None] = mapped_column(String(60))
    ply: Mapped[str | None] = mapped_column(String(30))
    yarn_type: Mapped[str | None] = mapped_column(String(80))
    colour: Mapped[str | None] = mapped_column(String(100))
    shade_code: Mapped[str | None] = mapped_column(String(60))
    pattern: Mapped[str | None] = mapped_column(String(120))
    fabric_construction: Mapped[str | None] = mapped_column(String(120))
    weave_type: Mapped[str | None] = mapped_column(String(120))
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    size_specification: Mapped[str | None] = mapped_column(String(120))
    gsm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    quality_grade: Mapped[str | None] = mapped_column(String(60))
    finish: Mapped[str | None] = mapped_column(String(100))

    # Current customer-requested order item attributes.
    brand: Mapped[str | None] = mapped_column(String(120))
    occasion: Mapped[str | None] = mapped_column(String(120))
    pure: Mapped[str | None] = mapped_column(String(120))
    weight: Mapped[str | None] = mapped_column(String(80))
    washcare: Mapped[str | None] = mapped_column(Text)
    custom_attributes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    produced_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=0, nullable=False)
    approved_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=0, nullable=False)
    dispatched_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=0, nullable=False)
    uom_code: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    order: Mapped["SalesOrder"] = relationship(back_populates="lines")


class OrderStatusEvent(Base):
    """Append-only record of order cancellation and restoration actions."""

    __tablename__ = "order_status_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('cancelled','restored')",
            name="ck_order_status_events_action",
        ),
        Index("ix_order_status_events_order_time", "order_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    quantity_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrderLineDetailsEvent(Base):
    """Append-only before/after history for customer order item specifications."""

    __tablename__ = "order_line_details_events"
    __table_args__ = (
        Index("ix_order_line_details_events_order_line_time",
              "order_id", "line_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    line_id: Mapped[int] = mapped_column(
        ForeignKey("sales_order_lines.id", ondelete="CASCADE"), nullable=False
    )
    changed_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
