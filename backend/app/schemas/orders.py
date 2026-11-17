from datetime import date, datetime
import re
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel, ConfigDict, Field, field_validator, model_validator
)


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = None
    mobile: str | None = None
    email: str | None = None
    state: str | None = None
    notes: str | None = None


class CustomerOut(BaseModel):
    id: int
    code: str
    name: str
    mobile: str | None = None
    email: str | None = None
    state: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderLineAttribute(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)

    @field_validator("name", "value")
    @classmethod
    def trim_attribute_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Attribute name and value cannot be blank.")
        return value


def validate_unique_attributes(attributes):
    names = [item.name.casefold() for item in attributes]
    if len(names) != len(set(names)):
        raise ValueError("Custom attribute names must be unique within an order item.")
    return attributes


class OrderLineCreate(BaseModel):
    product_id: int | None = None
    description: str = Field(min_length=1, max_length=250)

    # Retained for compatibility with older API clients and stored records.
    design_code: str | None = Field(default=None, max_length=80)
    material: str | None = Field(default=None, max_length=120)
    fibre_content: str | None = Field(default=None, max_length=200)
    yarn_count: str | None = Field(default=None, max_length=60)
    ply: str | None = Field(default=None, max_length=30)
    yarn_type: str | None = Field(default=None, max_length=80)
    colour: str | None = Field(default=None, max_length=100)
    shade_code: str | None = Field(default=None, max_length=60)
    pattern: str | None = Field(default=None, max_length=120)
    fabric_construction: str | None = Field(default=None, max_length=120)
    weave_type: str | None = Field(default=None, max_length=120)
    width_mm: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    size_specification: str | None = Field(default=None, max_length=120)
    gsm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    quality_grade: str | None = Field(default=None, max_length=60)
    finish: str | None = Field(default=None, max_length=100)

    brand: str | None = Field(default=None, max_length=120)
    occasion: str | None = Field(default=None, max_length=120)
    pure: str | None = Field(default=None, max_length=120)
    weight: str | None = Field(default=None, max_length=80)
    washcare: str | None = None
    custom_attributes: list[OrderLineAttribute] = Field(default_factory=list)

    ordered_qty: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    uom_code: str = Field(min_length=1, max_length=20)
    notes: str | None = None

    @model_validator(mode="after")
    def check_custom_attribute_names(self):
        validate_unique_attributes(self.custom_attributes)
        return self




def validate_four_digit_date(value):
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", value):
        raise ValueError("Date must use the exact YYYY-MM-DD format with a four-digit year.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid calendar date in YYYY-MM-DD format.")


class OrderCreate(BaseModel):
    customer_id: int
    order_date: date
    delivery_date: date
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    notes: str | None = None
    lines: list[OrderLineCreate] = Field(min_length=1)

    @field_validator("order_date", "delivery_date", mode="before")
    @classmethod
    def validate_order_dates(cls, value):
        return validate_four_digit_date(value)


class OrderLineEdit(OrderLineCreate):
    # Existing item ID; null means this is a newly added item.
    line_id: int | None = None


class OrderUpdate(BaseModel):
    customer_id: int
    order_date: date
    delivery_date: date
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    notes: str | None = None
    lines: list[OrderLineEdit] = Field(min_length=1)

    @field_validator("order_date", "delivery_date", mode="before")
    @classmethod
    def validate_order_dates(cls, value):
        return validate_four_digit_date(value)


class OrderProgressUpdate(BaseModel):
    produced_qty: Decimal = Field(ge=0, max_digits=16, decimal_places=3)
    approved_qty: Decimal = Field(ge=0, max_digits=16, decimal_places=3)
    dispatched_qty: Decimal = Field(ge=0, max_digits=16, decimal_places=3)


class OrderLineOut(BaseModel):
    id: int
    line_number: int
    product_id: int | None
    description: str
    design_code: str | None

    material: str | None = None
    fibre_content: str | None = None
    yarn_count: str | None = None
    ply: str | None = None
    yarn_type: str | None = None
    colour: str | None = None
    shade_code: str | None = None
    pattern: str | None = None
    fabric_construction: str | None = None
    weave_type: str | None = None
    width_mm: Decimal | None = None
    size_specification: str | None = None
    gsm: Decimal | None = None
    quality_grade: str | None = None
    finish: str | None = None

    brand: str | None = None
    occasion: str | None = None
    pure: str | None = None
    weight: str | None = None
    washcare: str | None = None
    custom_attributes: list[OrderLineAttribute] = Field(default_factory=list)

    ordered_qty: Decimal
    produced_qty: Decimal
    approved_qty: Decimal
    dispatched_qty: Decimal
    uom_code: str
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class OrderLineDetailsUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=250)
    ordered_qty: Decimal | None = Field(default=None, gt=0, max_digits=16, decimal_places=3)
    uom_code: str | None = Field(default=None, min_length=1, max_length=20)

    # Legacy fields remain accepted for compatibility.
    design_code: str | None = Field(default=None, max_length=80)
    material: str | None = Field(default=None, max_length=120)
    fibre_content: str | None = Field(default=None, max_length=200)
    yarn_count: str | None = Field(default=None, max_length=60)
    ply: str | None = Field(default=None, max_length=30)
    yarn_type: str | None = Field(default=None, max_length=80)
    colour: str | None = Field(default=None, max_length=100)
    shade_code: str | None = Field(default=None, max_length=60)
    pattern: str | None = Field(default=None, max_length=120)
    fabric_construction: str | None = Field(default=None, max_length=120)
    weave_type: str | None = Field(default=None, max_length=120)
    width_mm: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    size_specification: str | None = Field(default=None, max_length=120)
    gsm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    quality_grade: str | None = Field(default=None, max_length=60)
    finish: str | None = Field(default=None, max_length=100)

    brand: str | None = Field(default=None, max_length=120)
    occasion: str | None = Field(default=None, max_length=120)
    pure: str | None = Field(default=None, max_length=120)
    weight: str | None = Field(default=None, max_length=80)
    washcare: str | None = None
    custom_attributes: list[OrderLineAttribute] | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_custom_attribute_names(self):
        if self.custom_attributes is not None:
            validate_unique_attributes(self.custom_attributes)
        return self


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_id: int
    customer_name: str
    order_date: date
    delivery_date: date
    priority: str
    status: str
    notes: str | None
    created_at: datetime
    lines: list[OrderLineOut]

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: Literal["confirmed", "cancelled"]
    reason: str | None = Field(default=None, max_length=2000)
