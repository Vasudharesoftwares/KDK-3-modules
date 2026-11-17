from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index,
    Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        UniqueConstraint("company_id", "request_number",
                         name="uq_purchase_requests_number"),
        CheckConstraint(
            "status IN ('draft','approved','converted','cancelled')",
            name="ck_purchase_requests_status",
        ),
        Index("ix_purchase_requests_company_date", "company_id", "request_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id"))
    production_plan_id: Mapped[int | None] = mapped_column(ForeignKey("production_plans.id"))
    request_number: Mapped[str] = mapped_column(String(60), nullable=False)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PurchaseRequestLine(Base):
    __tablename__ = "purchase_request_lines"
    __table_args__ = (
        UniqueConstraint("request_id", "line_number",
                         name="uq_purchase_request_lines_number"),
        CheckConstraint("requested_qty > 0", name="ck_purchase_request_qty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    requested_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    uom_code: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "order_number",
                         name="uq_purchase_orders_number"),
        CheckConstraint(
            "status IN ('draft','issued','partially_received','received','cancelled')",
            name="ck_purchase_orders_status",
        ),
        Index("ix_purchase_orders_company_date", "company_id", "order_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), nullable=False)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requests.id"))
    order_number: Mapped[str] = mapped_column(String(60), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "line_number",
                         name="uq_purchase_order_lines_number"),
        CheckConstraint("ordered_qty > 0", name="ck_purchase_order_qty"),
        CheckConstraint("received_qty >= 0 AND received_qty <= ordered_qty",
                        name="ck_purchase_order_received_qty"),
        CheckConstraint("unit_rate >= 0", name="ck_purchase_order_rate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    request_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_request_lines.id")
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), default=0, nullable=False
    )
    uom_code: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint("company_id", "receipt_number",
                         name="uq_goods_receipts_number"),
        CheckConstraint(
            "status IN ('draft','posted','cancelled')",
            name="ck_goods_receipts_status",
        ),
        Index("ix_goods_receipts_company_date", "company_id", "receipt_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(60), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    inventory_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_transactions.id")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        UniqueConstraint("receipt_id", "line_number",
                         name="uq_goods_receipt_lines_number"),
        CheckConstraint("received_qty > 0", name="ck_grn_received_positive"),
        CheckConstraint("accepted_qty >= 0", name="ck_grn_accepted_nonnegative"),
        CheckConstraint("rejected_qty >= 0", name="ck_grn_rejected_nonnegative"),
        CheckConstraint("accepted_qty + rejected_qty = received_qty",
                        name="ck_grn_qty_split"),
        CheckConstraint("unit_cost >= 0", name="ck_grn_unit_cost"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False
    )
    order_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_lines.id"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    stock_stage_id: Mapped[int] = mapped_column(ForeignKey("stock_stages.id"), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    accepted_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
