from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = None
    mobile: str | None = None
    email: str | None = None
    gstin: str | None = Field(default=None, max_length=20)
    state: str | None = None
    notes: str | None = None

    @field_validator("code", "name")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class PurchaseLineCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    uom_code: str = Field(min_length=1, max_length=20)
    notes: str | None = None

    @field_validator("uom_code")
    @classmethod
    def trim_uom(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Unit cannot be blank.")
        return value


class PurchaseRequestCreate(BaseModel):
    request_date: date
    required_date: date | None = None
    sales_order_id: int | None = Field(default=None, gt=0)
    production_plan_id: int | None = Field(default=None, gt=0)
    notes: str | None = None
    lines: list[PurchaseLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def check_dates(self):
        if self.required_date and self.required_date < self.request_date:
            raise ValueError("Required date cannot be before request date.")
        return self


class PurchaseOrderLineCreate(BaseModel):
    product_id: int = Field(gt=0)
    request_line_id: int | None = Field(default=None, gt=0)
    ordered_qty: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    uom_code: str = Field(min_length=1, max_length=20)
    unit_rate: Decimal = Field(ge=0, max_digits=16, decimal_places=4)
    notes: str | None = None

    @field_validator("uom_code")
    @classmethod
    def trim_uom(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Unit cannot be blank.")
        return value


class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    request_id: int | None = Field(default=None, gt=0)
    order_date: date
    expected_date: date | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def check_dates(self):
        if self.expected_date and self.expected_date < self.order_date:
            raise ValueError("Expected date cannot be before order date.")
        return self


class PurchaseRequestStatusUpdate(BaseModel):
    status: Literal["approved", "cancelled"]


class PurchaseOrderStatusUpdate(BaseModel):
    status: Literal["issued", "cancelled"]


class SupplierOut(BaseModel):
    id: int
    code: str
    name: str
    contact_person: str | None
    mobile: str | None
    email: str | None
    gstin: str | None
    state: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptLineCreate(BaseModel):
    order_line_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    stock_stage_id: int = Field(gt=0)
    received_qty: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    accepted_qty: Decimal = Field(ge=0, max_digits=16, decimal_places=3)
    rejected_qty: Decimal = Field(ge=0, max_digits=16, decimal_places=3)
    unit_cost: Decimal = Field(ge=0, max_digits=16, decimal_places=4)
    rejection_reason: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_quantity_split(self):
        if self.accepted_qty + self.rejected_qty != self.received_qty:
            raise ValueError("Accepted quantity plus rejected quantity must equal received quantity.")
        return self


class GoodsReceiptCreate(BaseModel):
    order_id: int = Field(gt=0)
    receipt_date: date
    supplier_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    lines: list[GoodsReceiptLineCreate] = Field(min_length=1)


