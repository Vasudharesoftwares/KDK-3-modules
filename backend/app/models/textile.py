from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, Numeric,
    String, Text, Time, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductTextileSpec(Base):
    __tablename__ = "product_textile_specs"
    __table_args__ = (
        CheckConstraint(
            "width_mm IS NULL OR width_mm > 0",
            name="ck_textile_width_positive"
        ),
        CheckConstraint(
            "gsm IS NULL OR gsm > 0",
            name="ck_textile_gsm_positive"
        ),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True
    )
    fibre_content: Mapped[str | None] = mapped_column(String(200))
    material: Mapped[str | None] = mapped_column(String(120))
    yarn_count: Mapped[str | None] = mapped_column(String(60))
    ply: Mapped[str | None] = mapped_column(String(30))
    yarn_type: Mapped[str | None] = mapped_column(String(80))
    colour: Mapped[str | None] = mapped_column(String(100))
    shade_code: Mapped[str | None] = mapped_column(String(60))
    fabric_construction: Mapped[str | None] = mapped_column(String(120))
    weave_type: Mapped[str | None] = mapped_column(String(80))
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    gsm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    design_code: Mapped[str | None] = mapped_column(String(80))
    quality_grade: Mapped[str | None] = mapped_column(String(60))
    finish: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)


class MachineType(Base):
    __tablename__ = "machine_types"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "code",
            name="uq_machine_types_company_code"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "code",
            name="uq_machines_company_code"
        ),
        CheckConstraint(
            "loom_width_mm IS NULL OR loom_width_mm > 0",
            name="ck_machine_width_positive"
        ),
        CheckConstraint(
            "reed_count IS NULL OR reed_count > 0",
            name="ck_machine_reed_positive"
        ),
        CheckConstraint(
            "rpm IS NULL OR rpm > 0",
            name="ck_machine_rpm_positive"
        ),
        CheckConstraint(
            "head_count IS NULL OR head_count > 0",
            name="ck_machine_heads_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id"), nullable=False
    )
    machine_type_id: Mapped[int] = mapped_column(
        ForeignKey("machine_types.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model_number: Mapped[str | None] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    loom_width_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    reed_count: Mapped[int | None] = mapped_column()
    rpm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    head_count: Mapped[int | None] = mapped_column()
    installation_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "code",
            name="uq_shifts_company_code"
        ),
        CheckConstraint(
            "sequence_no > 0",
            name="ck_shift_sequence_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    sequence_no: Mapped[int] = mapped_column(default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "worker_code",
            name="uq_workers_company_code"
        ),
        CheckConstraint(
            "worker_type IN ('operator','karigar','helper','supervisor','other')",
            name="ck_worker_type"
        ),
        CheckConstraint(
            "pay_basis IN ('hourly','daily','piece_rate','monthly','other')",
            name="ck_worker_pay_basis"
        ),
        CheckConstraint(
            "default_rate >= 0",
            name="ck_worker_rate_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id")
    )
    party_id: Mapped[int | None] = mapped_column(
        ForeignKey("parties.id")
    )
    worker_code: Mapped[str] = mapped_column(String(40), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    worker_type: Mapped[str] = mapped_column(String(30), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(30))
    pay_basis: Mapped[str] = mapped_column(
        String(20), default="piece_rate", nullable=False
    )
    default_rate: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=0, nullable=False
    )
    joining_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class WorkerSkill(Base):
    __tablename__ = "worker_skills"
    __table_args__ = (
        UniqueConstraint(
            "worker_id", "machine_type_id",
            name="uq_worker_skills_worker_machine"
        ),
        CheckConstraint(
            "skill_level BETWEEN 1 AND 5",
            name="ck_worker_skill_level"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False
    )
    machine_type_id: Mapped[int] = mapped_column(
        ForeignKey("machine_types.id"), nullable=False
    )
    skill_level: Mapped[int] = mapped_column(default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
