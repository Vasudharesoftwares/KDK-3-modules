from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ProductionPlanCreate(BaseModel):
    sales_order_line_id: int = Field(gt=0)
    planned_qty: Decimal = Field(
        gt=0, max_digits=16, decimal_places=3
    )
    planned_start_date: date
    target_end_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.target_end_date and self.target_end_date < self.planned_start_date:
            raise ValueError("Target end date cannot be before planned start date.")
        return self


class ProductionPlanUpdate(BaseModel):
    sales_order_line_id: int = Field(gt=0)
    planned_qty: Decimal = Field(
        gt=0, max_digits=16, decimal_places=3
    )
    planned_start_date: date
    target_end_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.target_end_date and self.target_end_date < self.planned_start_date:
            raise ValueError("Target end date cannot be before planned start date.")
        return self


class PlanningAllocationCreate(BaseModel):
    machine_name: str = Field(min_length=1, max_length=120)
    worker_name: str = Field(min_length=1, max_length=120)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_allocation(self):
        self.machine_name = self.machine_name.strip()
        self.worker_name = self.worker_name.strip()
        if not self.machine_name or not self.worker_name:
            raise ValueError("Machine name and worker name are required.")
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise ValueError("Start date and time must include a timezone.")
        if self.ends_at.tzinfo is None or self.ends_at.utcoffset() is None:
            raise ValueError("End date and time must include a timezone.")
        if self.ends_at <= self.starts_at:
            raise ValueError("End date and time must be after start date and time.")
        return self


class PlanningActualUpdate(BaseModel):
    actual_qty: Decimal = Field(
        ge=0, max_digits=16, decimal_places=3
    )
    reason: str | None = Field(default=None, max_length=2000)


class PlanningStatusUpdate(BaseModel):
    status: Literal["scheduled", "in_progress", "completed", "cancelled"]
    reason: str | None = Field(default=None, max_length=2000)
