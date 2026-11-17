from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ProductionShiftEntryCreate(BaseModel):
    machine_id: int = Field(gt=0)
    shift_id: int = Field(gt=0)
    work_date: date
    unit_code: Literal["metres", "pieces"]
    target_output: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    actual_output: Decimal = Field(ge=0, max_digits=16, decimal_places=3)
    notes: str | None = Field(default=None, max_length=2000)


class ProductionMaterialRecipeLineCreate(BaseModel):
    line_number: int = Field(gt=0)
    material_product_id: int = Field(gt=0)
    stock_stage_id: int = Field(gt=0)
    quantity_per_basis: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    quantity_uom_code: Literal["metres", "pieces", "kg"]
    wastage_percent: Decimal = Field(default=0, ge=0, le=100, max_digits=7, decimal_places=3)
    notes: str | None = Field(default=None, max_length=2000)


class ProductionMaterialRecipeCreate(BaseModel):
    product_id: int = Field(gt=0)
    recipe_code: str = Field(min_length=1, max_length=60)
    design_code: str | None = Field(default=None, max_length=80)
    basis_quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    basis_uom_code: Literal["metres", "pieces", "kg"]
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[ProductionMaterialRecipeLineCreate] = Field(min_length=1)


class MachineStandardRPMUpdate(BaseModel):
    standard_rpm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class MachineRPMReadingCreate(BaseModel):
    machine_id: int = Field(gt=0)
    recorded_at: datetime
    actual_rpm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
