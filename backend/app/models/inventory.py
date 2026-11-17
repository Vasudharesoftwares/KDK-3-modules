from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint,
    func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockStage(Base):
    __tablename__ = "stock_stages"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_stock_stages_company_code"),
        CheckConstraint(
            "stage_type IN ('raw_material','grey_fabric','work_in_progress',"
            "'finished_good','scrap','other')",
            name="ck_stock_stage_type"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(30), nullable=False)
    tracks_rolls: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InventoryLot(Base):
    __tablename__ = "inventory_lots"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "product_id", "lot_number",
            name="uq_inventory_lot_product_number"
        ),
        CheckConstraint(
            "lot_type IN ('supplier','yarn','dye','production','general','other')",
            name="ck_inventory_lot_type"
        ),
        Index("ix_inventory_lots_company_product", "company_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False)
    lot_type: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    parent_lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id"))
    dye_lot_number: Mapped[str | None] = mapped_column(String(100))
    received_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FabricRoll(Base):
    __tablename__ = "fabric_rolls"
    __table_args__ = (
        UniqueConstraint("company_id", "roll_number", name="uq_fabric_roll_company_number"),
        CheckConstraint("original_length_m > 0", name="ck_roll_original_length_positive"),
        CheckConstraint("current_length_m >= 0", name="ck_roll_current_length_nonnegative"),
        CheckConstraint("net_weight_kg IS NULL OR net_weight_kg >= 0",
                        name="ck_roll_weight_nonnegative"),
        CheckConstraint("width_mm IS NULL OR width_mm > 0",
                        name="ck_roll_width_positive"),
        CheckConstraint("gsm IS NULL OR gsm > 0", name="ck_roll_gsm_positive"),
        CheckConstraint(
            "status IN ('available','reserved','issued','consumed','hold','returned','scrapped')",
            name="ck_fabric_roll_status"
        ),
        Index("ix_fabric_rolls_product_status", "company_id", "product_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    warehouse_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse_locations.id")
    )
    stock_stage_id: Mapped[int] = mapped_column(
        ForeignKey("stock_stages.id"), nullable=False
    )
    roll_number: Mapped[str] = mapped_column(String(100), nullable=False)
    original_length_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    current_length_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    net_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    gsm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    shade_code: Mapped[str | None] = mapped_column(String(60))
    design_code: Mapped[str | None] = mapped_column(String(80))
    quality_grade: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        UniqueConstraint("company_id", "transaction_number",
                         name="uq_inventory_transaction_number"),
        UniqueConstraint("company_id", "idempotency_key",
                         name="uq_inventory_transaction_idempotency"),
        CheckConstraint(
            "transaction_type IN ('opening','receipt','issue','transfer',"
            "'production_receipt','production_issue','adjustment',"
            "'sales_dispatch','purchase_return','jobwork_issue',"
            "'jobwork_receipt','roll_split','roll_merge','other')",
            name="ck_inventory_transaction_type"
        ),
        CheckConstraint(
            "status IN ('draft','posted','cancelled')",
            name="ck_inventory_transaction_status"
        ),
        Index("ix_inventory_transactions_company_date", "company_id", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    transaction_number: Mapped[str] = mapped_column(String(60), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(60))
    source_id: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryTransactionLine(Base):
    __tablename__ = "inventory_transaction_lines"
    __table_args__ = (
        UniqueConstraint("transaction_id", "line_number",
                         name="uq_inventory_transaction_line_number"),
        CheckConstraint("quantity > 0", name="ck_inventory_line_quantity_positive"),
        CheckConstraint("direction IN ('in','out')", name="ck_inventory_line_direction"),
        CheckConstraint("unit_cost >= 0", name="ck_inventory_line_cost_nonnegative"),
        CheckConstraint("line_value >= 0", name="ck_inventory_line_value_nonnegative"),
        Index("ix_inventory_lines_product", "product_id"),
        Index("ix_inventory_lines_roll", "roll_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    stock_stage_id: Mapped[int] = mapped_column(ForeignKey("stock_stages.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id"))
    roll_id: Mapped[int | None] = mapped_column(ForeignKey("fabric_rolls.id"))
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), default=0, nullable=False)
    line_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "product_id", "warehouse_id", "stock_stage_id",
            name="uq_stock_balance_dimension"
        ),
        CheckConstraint("quantity_on_hand >= 0",
                        name="ck_stock_balance_quantity_nonnegative"),
        CheckConstraint("inventory_value >= 0",
                        name="ck_stock_balance_value_nonnegative"),
        CheckConstraint("average_unit_cost >= 0",
                        name="ck_stock_balance_cost_nonnegative"),
        Index("ix_stock_balances_company_product", "company_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    stock_stage_id: Mapped[int] = mapped_column(ForeignKey("stock_stages.id"), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), default=0, nullable=False
    )
    inventory_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=0, nullable=False
    )
    average_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), default=0, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class StockLedger(Base):
    __tablename__ = "stock_ledger"
    __table_args__ = (
        UniqueConstraint("transaction_line_id", name="uq_stock_ledger_transaction_line"),
        CheckConstraint("quantity_in >= 0 AND quantity_out >= 0",
                        name="ck_stock_ledger_quantities_nonnegative"),
        CheckConstraint("NOT (quantity_in > 0 AND quantity_out > 0)",
                        name="ck_stock_ledger_one_direction"),
        CheckConstraint("unit_cost >= 0", name="ck_stock_ledger_cost_nonnegative"),
        Index("ix_stock_ledger_product_date", "company_id", "product_id", "posted_at"),
        Index("ix_stock_ledger_roll", "roll_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    transaction_line_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_transaction_lines.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    stock_stage_id: Mapped[int] = mapped_column(ForeignKey("stock_stages.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id"))
    roll_id: Mapped[int | None] = mapped_column(ForeignKey("fabric_rolls.id"))
    quantity_in: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=0, nullable=False)
    quantity_out: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=0, nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    value_in: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    value_out: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    value_balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
