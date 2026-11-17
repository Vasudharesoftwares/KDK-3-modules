from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductionShiftEntry(Base):
    __tablename__ = "production_shift_entries"
    __table_args__ = (
        CheckConstraint(
            "unit_code IN ('metres', 'pieces')",
            name="ck_production_shift_entry_unit",
        ),
        CheckConstraint(
            "target_output > 0",
            name="ck_production_shift_entry_target_positive",
        ),
        CheckConstraint(
            "actual_output >= 0",
            name="ck_production_shift_entry_actual_nonnegative",
        ),
        Index(
            "ix_production_shift_entries_company_date",
            "company_id", "work_date",
        ),
        Index(
            "ix_production_shift_entries_machine_date",
            "machine_id", "work_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"), nullable=False
    )
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False
    )
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("shifts.id"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit_code: Mapped[str] = mapped_column(String(20), nullable=False)
    target_output: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), nullable=False
    )
    actual_output: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductionMaterialRecipe(Base):
    __tablename__ = "production_material_recipes"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "product_id", "recipe_code", "version",
            name="uq_production_recipe_version",
        ),
        CheckConstraint("basis_quantity > 0",
                        name="ck_production_recipe_basis_positive"),
        CheckConstraint(
            "basis_uom_code IN ('metres','pieces','kg')",
            name="ck_production_recipe_basis_uom",
        ),
        Index(
            "ix_production_recipe_product_active",
            "company_id", "product_id", "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    recipe_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    design_code: Mapped[str | None] = mapped_column(String(80))
    basis_quantity: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), nullable=False
    )
    basis_uom_code: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductionMaterialRecipeLine(Base):
    __tablename__ = "production_material_recipe_lines"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id", "line_number",
            name="uq_production_recipe_line_number",
        ),
        CheckConstraint(
            "quantity_per_basis > 0",
            name="ck_production_recipe_line_quantity_positive",
        ),
        CheckConstraint(
            "wastage_percent >= 0 AND wastage_percent <= 100",
            name="ck_production_recipe_line_wastage_range",
        ),
        CheckConstraint(
            "quantity_uom_code IN ('metres','pieces','kg')",
            name="ck_production_recipe_line_uom",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("production_material_recipes.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    stock_stage_id: Mapped[int] = mapped_column(
        ForeignKey("stock_stages.id"), nullable=False
    )
    quantity_per_basis: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), nullable=False
    )
    quantity_uom_code: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    wastage_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 3), default=0, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)


class MachineRPMReading(Base):
    __tablename__ = "machine_rpm_readings"
    __table_args__ = (
        CheckConstraint(
            "actual_rpm > 0",
            name="ck_machine_rpm_reading_actual_positive",
        ),
        CheckConstraint(
            "standard_rpm > 0",
            name="ck_machine_rpm_reading_standard_positive",
        ),
        Index(
            "ix_machine_rpm_readings_company_machine_time",
            "company_id", "machine_id", "recorded_at",
        ),
        Index(
            "ix_machine_rpm_readings_company_time",
            "company_id", "recorded_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"), nullable=False
    )
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_rpm: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    standard_rpm: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
