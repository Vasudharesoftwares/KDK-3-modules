from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.orders import OrderLineDetailsEvent
from app.models.planning import ProductionPlan
from app.models.purchases import PurchaseRequest
from app.models import Company, Branch, Party, PartyAddress, Product, SalesOrder, SalesOrderLine, OrderStatusEvent
from app.schemas.orders import (
    CustomerCreate,
    CustomerOut,
    OrderCreate,
    OrderUpdate,
    OrderProgressUpdate,
    OrderLineDetailsUpdate,
    OrderStatusUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["Orders"])


def active_company(db: Session) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.id)
    )
    if not company:
        raise HTTPException(409, "Factory company is not initialized.")
    return company


def order_to_dict(order: SalesOrder, customer: Party, db: Session) -> dict:
    line_fields = (
        "id", "line_number", "product_id", "description", "design_code",
        "material", "fibre_content", "yarn_count", "ply", "yarn_type",
        "colour", "shade_code", "pattern", "fabric_construction",
        "weave_type", "width_mm", "size_specification", "gsm",
        "quality_grade", "finish", "brand", "occasion", "pure", "weight",
        "washcare", "custom_attributes", "ordered_qty", "produced_qty",
        "approved_qty", "dispatched_qty", "uom_code", "notes",
    )

    addresses = db.scalars(
        select(PartyAddress)
        .where(PartyAddress.party_id == customer.id)
        .order_by(PartyAddress.is_default.desc(), PartyAddress.id)
    ).all()

    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "customer_name": customer.name,
        "customer": {
            "id": customer.id,
            "code": customer.code,
            "name": customer.name,
            "contact_person": customer.contact_person,
            "mobile": customer.mobile,
            "email": customer.email,
            "state": customer.state,
            "gstin": customer.gstin,
            "pan": customer.pan,
            "notes": customer.notes,
            "is_active": customer.is_active,
        },
        "customer_addresses": [
            {
                "id": a.id,
                "address_type": a.address_type,
                "address": a.address,
                "city": a.city,
                "district": a.district,
                "state": a.state,
                "pin_code": a.pin_code,
                "country": a.country,
                "is_default": a.is_default,
            }
            for a in addresses
        ],
        "order_date": order.order_date,
        "delivery_date": order.delivery_date,
        "priority": order.priority,
        "status": order.status,
        "notes": order.notes,
        "created_at": order.created_at,
        "lines": [
            {field: getattr(line, field) for field in line_fields}
            for line in order.lines
        ],
    }

@router.get("/lookups/customers", response_model=list[CustomerOut])
def customer_lookup(db: Session = Depends(get_db)):
    company = active_company(db)
    return db.scalars(
        select(Party)
        .where(
            Party.company_id == company.id,
            Party.party_type == "customer",
            Party.is_active.is_(True),
        )
        .order_by(Party.name)
    ).all()


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    company = active_company(db)
    code = payload.code.strip()
    name = payload.name.strip()

    if not code or not name:
        raise HTTPException(422, "Customer code and name are required.")

    duplicate = db.scalar(
        select(Party).where(
            Party.company_id == company.id,
            Party.code == code,
        )
    )
    if duplicate:
        raise HTTPException(409, "Customer code already exists.")

    customer = Party(
        company_id=company.id,
        code=code,
        party_type="customer",
        name=name,
        contact_person=payload.contact_person,
        mobile=payload.mobile,
        email=payload.email,
        state=payload.state,
        notes=payload.notes,
        balance_type="debit",
        credit_limit=0,
        opening_balance=0,
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/lookups/products")
def product_lookup(db: Session = Depends(get_db)):
    company = active_company(db)
    products = db.scalars(
        select(Product)
        .where(
            Product.company_id == company.id,
            Product.is_active.is_(True),
        )
        .order_by(Product.name)
    ).all()

    return [
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "product_type": product.product_type,
        }
        for product in products
    ]


@router.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    company = active_company(db)

    rows = db.execute(
        select(SalesOrder, Party)
        .join(Party, Party.id == SalesOrder.customer_id)
        .options(selectinload(SalesOrder.lines))
        .where(SalesOrder.company_id == company.id)
        .order_by(SalesOrder.id.asc())
    ).all()

    return [
        order_to_dict(order, customer, db)
        for order, customer in rows
    ]


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    company = active_company(db)

    row = db.execute(
        select(SalesOrder, Party)
        .join(Party, Party.id == SalesOrder.customer_id)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
    ).first()

    if not row:
        raise HTTPException(404, "Order not found.")

    order, customer = row
    return order_to_dict(order, customer, db)


@router.post("/orders", status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    company = active_company(db)

    if payload.delivery_date < payload.order_date:
        raise HTTPException(422, "Delivery date cannot be before order date.")

    branch = db.scalar(
        select(Branch)
        .where(
            Branch.company_id == company.id,
            Branch.is_active.is_(True),
        )
        .order_by(Branch.id)
    )
    if not branch:
        raise HTTPException(409, "No active factory branch is configured.")

    customer = db.scalar(
        select(Party).where(
            Party.id == payload.customer_id,
            Party.company_id == company.id,
            Party.party_type == "customer",
            Party.is_active.is_(True),
        )
    )
    if not customer:
        raise HTTPException(422, "Select a valid active customer.")

    for line in payload.lines:
        if line.product_id is not None:
            product = db.scalar(
                select(Product).where(
                    Product.id == line.product_id,
                    Product.company_id == company.id,
                    Product.is_active.is_(True),
                )
            )
            if not product:
                raise HTTPException(422, f"Invalid product ID: {line.product_id}")

        if not line.description.strip() or not line.uom_code.strip():
            raise HTTPException(422, "Each order line needs a description and unit.")

    # Serialize number allocation for this company.
    db.scalar(
        select(Company)
        .where(Company.id == company.id)
        .with_for_update()
    )

    # Allocate a permanent, non-reusable number from PostgreSQL's ID sequence.
    # Deleted orders leave gaps; their order numbers are never assigned again.
    allocated_order_id = db.execute(
        text("SELECT nextval('public.sales_orders_id_seq')")
    ).scalar_one()

    order_number = (
        f"KDK-SO-{payload.order_date.year}-{allocated_order_id:05d}"
    )

    order = SalesOrder(
        id=allocated_order_id,
        company_id=company.id,
        branch_id=branch.id,
        customer_id=customer.id,
        order_number=order_number,
        order_date=payload.order_date,
        delivery_date=payload.delivery_date,
        priority=payload.priority,
        status="draft",
        notes=payload.notes,
    )

    for index, line in enumerate(payload.lines, start=1):
        order.lines.append(
            SalesOrderLine(
                line_number=index,
                product_id=line.product_id,
                description=line.description.strip(),
                design_code=line.design_code,
                material=line.material,
                fibre_content=line.fibre_content,
                yarn_count=line.yarn_count,
                ply=line.ply,
                yarn_type=line.yarn_type,
                colour=line.colour,
                shade_code=line.shade_code,
                pattern=line.pattern,
                fabric_construction=line.fabric_construction,
                weave_type=line.weave_type,
                width_mm=line.width_mm,
                size_specification=line.size_specification,
                gsm=line.gsm,
                quality_grade=line.quality_grade,
                finish=line.finish,
                brand=line.brand,
                occasion=line.occasion,
                pure=line.pure,
                weight=line.weight,
                washcare=line.washcare,
                custom_attributes=[item.model_dump() for item in line.custom_attributes],
                ordered_qty=line.ordered_qty,
                produced_qty=Decimal("0"),
                approved_qty=Decimal("0"),
                dispatched_qty=Decimal("0"),
                uom_code=line.uom_code.strip(),
                notes=line.notes,
            )
        )

    db.add(order)
    db.commit()
    db.refresh(order)

    return order_to_dict(order, customer, db)



@router.put("/orders/{order_id}")
def update_order(
    order_id: int,
    payload: OrderUpdate,
    db: Session = Depends(get_db),
):
    """Safely edit an order while preserving all recorded factory progress."""
    company = active_company(db)

    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Order not found.")

    if order.status == "cancelled":
        raise HTTPException(409, "Cancelled orders are read-only. Restore the order before editing.")

    if payload.delivery_date < payload.order_date:
        raise HTTPException(422, "Delivery date cannot be before order date.")

    customer = db.scalar(
        select(Party).where(
            Party.id == payload.customer_id,
            Party.company_id == company.id,
            Party.party_type == "customer",
            Party.is_active.is_(True),
        )
    )
    if not customer:
        raise HTTPException(422, "Select a valid active customer.")

    submitted_ids = [line.line_id for line in payload.lines if line.line_id is not None]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(422, "An order item was submitted more than once.")

    existing_by_id = {line.id: line for line in order.lines}
    unknown_ids = set(submitted_ids) - set(existing_by_id)
    if unknown_ids:
        raise HTTPException(422, "One or more order items do not belong to this order.")

    retained_ids = set(submitted_ids)
    removed_lines = [
        line for line in order.lines
        if line.id not in retained_ids
    ]

    # Never remove a line with production/quality/dispatch progress or
    # a specification audit trail.
    for line in removed_lines:
        if any(value > 0 for value in (
            line.produced_qty, line.approved_qty, line.dispatched_qty
        )):
            raise HTTPException(
                409,
                f'Item "{line.description}" has manufacturing progress and cannot be removed.',
            )

        history_count = db.scalar(
            select(func.count(OrderLineDetailsEvent.id)).where(
                OrderLineDetailsEvent.order_id == order.id,
                OrderLineDetailsEvent.line_id == line.id,
            )
        ) or 0
        if history_count:
            raise HTTPException(
                409,
                f'Item "{line.description}" has an audit history and cannot be removed.',
            )

    # Validate every submitted line before changing any ORM objects.
    for item in payload.lines:
        if not item.description.strip():
            raise HTTPException(422, "Every item needs a Product Name.")

        if not item.uom_code.strip():
            raise HTTPException(422, "Every item needs a Unit.")

        if item.product_id is not None:
            product = db.scalar(
                select(Product).where(
                    Product.id == item.product_id,
                    Product.company_id == company.id,
                    Product.is_active.is_(True),
                )
            )
            if not product:
                raise HTTPException(422, f"Invalid product ID: {item.product_id}")

        if item.line_id is not None:
            old_line = existing_by_id[item.line_id]
            new_qty = item.ordered_qty
            recorded = max(
                old_line.produced_qty,
                old_line.approved_qty,
                old_line.dispatched_qty,
            )

            # An unchanged legacy quantity remains editable even if the
            # factory has recorded overproduction against it.
            if new_qty < old_line.ordered_qty and new_qty < recorded:
                raise HTTPException(
                    422,
                    f'Ordered quantity for "{old_line.description}" cannot be reduced below recorded progress ({recorded}).',
                )

            if item.uom_code.strip() != old_line.uom_code and any(
                value > 0 for value in (
                    old_line.produced_qty,
                    old_line.approved_qty,
                    old_line.dispatched_qty,
                )
            ):
                raise HTTPException(
                    409,
                    f'Unit for "{old_line.description}" cannot be changed after production progress.',
                )

    # Update order header.
    order.customer_id = customer.id
    order.order_date = payload.order_date
    order.delivery_date = payload.delivery_date
    order.priority = payload.priority
    order.notes = payload.notes

    # Move current line numbers out of the positive range first so that
    # reordering does not collide with the unique (order_id, line_number) key.
    for line in order.lines:
        line.line_number = -line.id
    db.flush()

    # Remove only the previously validated untouched lines.
    for line in removed_lines:
        order.lines.remove(line)

    editable_fields = (
        "product_id", "description", "design_code", "material",
        "fibre_content", "yarn_count", "ply", "yarn_type", "colour",
        "shade_code", "pattern", "fabric_construction", "weave_type",
        "width_mm", "size_specification", "gsm", "quality_grade",
        "finish", "brand", "occasion", "pure", "weight", "washcare",
        "custom_attributes", "ordered_qty", "uom_code", "notes",
    )

    for position, item in enumerate(payload.lines, start=1):
        values = item.model_dump(exclude={"line_id"}, exclude_unset=True)

        # Normalise user-entered text and JSON attributes.
        for key, value in list(values.items()):
            if isinstance(value, str):
                values[key] = value.strip() or None

        if "description" not in values:
            values["description"] = item.description.strip()
        if "uom_code" not in values:
            values["uom_code"] = item.uom_code.strip()

        if "custom_attributes" in values:
            values["custom_attributes"] = [
                attribute.model_dump() if hasattr(attribute, "model_dump") else attribute
                for attribute in (values["custom_attributes"] or [])
            ]

        if item.line_id is None:
            # New lines always start with zero progress.
            all_values = item.model_dump(exclude={"line_id"})
            for key, value in list(all_values.items()):
                if isinstance(value, str):
                    all_values[key] = value.strip() or None
            all_values["custom_attributes"] = [
                attribute.model_dump() if hasattr(attribute, "model_dump") else attribute
                for attribute in (all_values.get("custom_attributes") or [])
            ]

            new_line = SalesOrderLine(
                line_number=-100000000 - position,
                produced_qty=Decimal("0"),
                approved_qty=Decimal("0"),
                dispatched_qty=Decimal("0"),
                **all_values,
            )
            order.lines.append(new_line)
            continue

        line = existing_by_id[item.line_id]
        changes = {}

        for key, new_value in values.items():
            if key not in editable_fields:
                continue

            old_value = getattr(line, key)
            if old_value != new_value:
                def audit_value(value):
                    if isinstance(value, Decimal):
                        return str(value)
                    if isinstance(value, list):
                        return [
                            entry.model_dump() if hasattr(entry, "model_dump") else entry
                            for entry in value
                        ]
                    return value

                changes[key] = {
                    "old": audit_value(old_value),
                    "new": audit_value(new_value),
                }
                setattr(line, key, new_value)

        if changes:
            db.add(OrderLineDetailsEvent(
                order_id=order.id,
                line_id=line.id,
                changed_fields=changes,
            ))

    db.flush()

    # Apply the final display order after all temporary numbers are unique.
    submitted_existing = {
        line.id: line for line in order.lines if line.id is not None
    }
    for position, item in enumerate(payload.lines, start=1):
        if item.line_id is not None:
            submitted_existing[item.line_id].line_number = position
        else:
            # Newly appended lines are ordered by their position in payload.
            new_candidates = [
                line for line in order.lines
                if line.id is None
            ]
            # The ORM assigns IDs during flush; new line ordering is handled
            # in the next flush and then normalised below.
    db.flush()

    # Rebuild the exact submitted line sequence, including newly inserted rows.
    current_lines = list(order.lines)
    used = set()
    ordered_lines = []
    for item in payload.lines:
        if item.line_id is not None:
            match = next(line for line in current_lines if line.id == item.line_id)
        else:
            match = next(
                line for line in current_lines
                if line.id not in used and line.id not in existing_by_id
            )
        ordered_lines.append(match)
        used.add(match.id)

    for position, line in enumerate(ordered_lines, start=1):
        line.line_number = position

    db.commit()
    db.refresh(order)

    customer = db.get(Party, order.customer_id)
    return order_to_dict(order, customer, db)


@router.delete("/orders/{order_id}")
def delete_draft_order(
    order_id: int,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Order not found.")

    if order.status not in ("draft", "cancelled"):
        raise HTTPException(
            409,
            "Only draft or cancelled orders can be permanently deleted."
        )

    if any(
        line.produced_qty > 0 or line.approved_qty > 0 or line.dispatched_qty > 0
        for line in order.lines
    ):
        raise HTTPException(
            409,
            "This order has manufacturing, approval or dispatch progress and cannot be deleted."
        )

    production_plan_count = db.scalar(
        select(func.count(ProductionPlan.id))
        .where(ProductionPlan.sales_order_id == order.id)
    ) or 0

    purchase_request_count = db.scalar(
        select(func.count(PurchaseRequest.id))
        .where(PurchaseRequest.sales_order_id == order.id)
    ) or 0

    if production_plan_count:
        raise HTTPException(
            409,
            "This order is linked to production plans. Remove or resolve those plans first."
        )

    if purchase_request_count:
        raise HTTPException(
            409,
            "This order is linked to purchase requests. Remove or resolve those requests first."
        )

    if order.status == "draft":
        status_history = db.scalar(
            select(func.count(OrderStatusEvent.id))
            .where(OrderStatusEvent.order_id == order.id)
        ) or 0
        detail_history = db.scalar(
            select(func.count(OrderLineDetailsEvent.id))
            .where(OrderLineDetailsEvent.order_id == order.id)
        ) or 0

        if status_history or detail_history:
            raise HTTPException(
                409,
                "This draft order has audit history and cannot be permanently deleted."
            )

    order_number = order.order_number
    db.delete(order)
    db.commit()

    return {
        "id": order_id,
        "order_number": order_number,
        "message": "Eligible order permanently deleted.",
    }


@router.post("/orders/{order_id}/close")
def close_order(
    order_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Archive an order with a mandatory reason and immutable quantity snapshot."""
    company = active_company(db)
    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Order not found.")
    if order.status == "cancelled":
        raise HTTPException(409, "This order is already archived.")

    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(422, "An archive reason is required.")
    if len(reason) > 2000:
        raise HTTPException(422, "The archive reason cannot exceed 2000 characters.")

    previous_status = order.status
    snapshot = [
        {
            "line_id": line.id,
            "ordered_qty": str(line.ordered_qty),
            "produced_qty": str(line.produced_qty),
            "approved_qty": str(line.approved_qty),
            "dispatched_qty": str(line.dispatched_qty),
        }
        for line in order.lines
    ]

    order.cancelled_from_status = previous_status
    order.cancellation_reason = reason
    order.cancelled_at = datetime.now(timezone.utc)
    order.status = "cancelled"

    db.add(OrderStatusEvent(
        order_id=order.id,
        action="cancelled",
        from_status=previous_status,
        to_status="cancelled",
        reason=reason,
        quantity_snapshot=snapshot,
    ))

    db.commit()
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "message": "Order archived. Production, dispatch and audit history are preserved.",
        "quantity_snapshot": snapshot,
    }


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Order not found.")

    if payload.status == "cancelled":
        if order.status == "cancelled":
            raise HTTPException(409, "This order is already cancelled.")

        if any(line.dispatched_qty > 0 for line in order.lines):
            raise HTTPException(
                409,
                "This order has dispatched quantities. Ordinary cancellation is blocked; contact an administrator for controlled closure.",
            )

        reason = (payload.reason or "").strip()
        if not reason:
            raise HTTPException(422, "Enter a reason for cancelling this order.")

        previous_status = order.status
        snapshot = [
            {
                "line_id": line.id,
                "ordered_qty": str(line.ordered_qty),
                "produced_qty": str(line.produced_qty),
                "approved_qty": str(line.approved_qty),
                "dispatched_qty": str(line.dispatched_qty),
            }
            for line in order.lines
        ]

        order.cancelled_from_status = previous_status
        order.cancellation_reason = reason
        order.cancelled_at = datetime.now(timezone.utc)
        order.status = "cancelled"

        db.add(OrderStatusEvent(
            order_id=order.id,
            action="cancelled",
            from_status=previous_status,
            to_status="cancelled",
            reason=reason,
            quantity_snapshot=snapshot,
        ))

    else:
        if order.status == "cancelled":
            raise HTTPException(409, "Restore this order before changing its status.")
        if order.status in ("completed", "in_production", "confirmed"):
            raise HTTPException(409, "This order has already been confirmed.")
        order.status = "confirmed"

    db.commit()
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "cancelled_from_status": order.cancelled_from_status,
    }


@router.post("/orders/{order_id}/restore")
def restore_order(
    order_id: int,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Order not found.")
    if order.status != "cancelled":
        raise HTTPException(409, "Only cancelled orders can be restored.")

    previous_status = order.cancelled_from_status
    if previous_status not in ("draft", "confirmed", "in_production", "completed"):
        raise HTTPException(
            409,
            "The original order status is unavailable. Contact an administrator.",
        )

    snapshot = [
        {
            "line_id": line.id,
            "ordered_qty": str(line.ordered_qty),
            "produced_qty": str(line.produced_qty),
            "approved_qty": str(line.approved_qty),
            "dispatched_qty": str(line.dispatched_qty),
        }
        for line in order.lines
    ]

    # Deliberately do not modify quantities or replay inventory/dispatch actions.
    order.status = previous_status
    order.cancelled_from_status = None
    order.cancellation_reason = None
    order.cancelled_at = None

    db.add(OrderStatusEvent(
        order_id=order.id,
        action="restored",
        from_status="cancelled",
        to_status=previous_status,
        reason="Restored to the status saved at cancellation.",
        quantity_snapshot=snapshot,
    ))

    db.commit()
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "message": "Order restored. Existing production and dispatch quantities were preserved.",
    }


@router.get("/orders/{order_id}/history")
def order_status_history(
    order_id: int,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(SalesOrder.id).where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
    )
    if order is None:
        raise HTTPException(404, "Order not found.")

    events = db.scalars(
        select(OrderStatusEvent)
        .where(OrderStatusEvent.order_id == order_id)
        .order_by(OrderStatusEvent.occurred_at, OrderStatusEvent.id)
    ).all()

    return [
        {
            "id": event.id,
            "action": event.action,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "reason": event.reason,
            "quantity_snapshot": event.quantity_snapshot,
            "occurred_at": event.occurred_at,
        }
        for event in events
    ]




@router.patch("/orders/{order_id}/lines/{line_id}/details")
def update_order_line_details(
    order_id: int,
    line_id: int,
    payload: OrderLineDetailsUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Order not found.")

    if order.status == "cancelled":
        raise HTTPException(409, "Cancelled orders are read-only. Restore the order before editing.")

    line = next((item for item in order.lines if item.id == line_id), None)
    if not line:
        raise HTTPException(404, "Order item not found in this order.")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, "Enter at least one field to update.")

    if "description" in updates:
        description = updates["description"]
        if description is None or not description.strip():
            raise HTTPException(422, "Product Name cannot be blank.")
        updates["description"] = description.strip()

    if "ordered_qty" in updates:
        new_qty = updates["ordered_qty"]
        if new_qty is None or new_qty <= 0:
            raise HTTPException(422, "Ordered Quantity must be greater than zero.")
        minimum_qty = max(line.produced_qty, line.approved_qty, line.dispatched_qty)
        if new_qty < minimum_qty:
            raise HTTPException(
                422,
                f"Ordered Quantity cannot be less than the recorded progress ({minimum_qty}).",
            )

    if "uom_code" in updates:
        new_unit = updates["uom_code"]
        if new_unit is None or not new_unit.strip():
            raise HTTPException(422, "Unit cannot be blank.")
        if new_unit.strip() != line.uom_code and any(
            value > 0 for value in (
                line.produced_qty, line.approved_qty, line.dispatched_qty
            )
        ):
            raise HTTPException(
                409,
                "Unit cannot be changed after production or dispatch progress has been recorded.",
            )
        updates["uom_code"] = new_unit.strip()

    for key, value in list(updates.items()):
        if isinstance(value, str):
            value = value.strip()
            updates[key] = value if value else (None if key != "description" else value)

    if "custom_attributes" in updates and updates["custom_attributes"] is None:
        raise HTTPException(422, "Custom attributes must be a list; use an empty list to clear them.")

    # SQLAlchemy JSON columns must receive JSON-compatible dictionaries,
    # not Pydantic model instances.
    if "custom_attributes" in updates:
        updates["custom_attributes"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in updates["custom_attributes"]
        ]

    changes = {}
    for key, new_value in updates.items():
        old_value = getattr(line, key)
        if old_value != new_value:
            def audit_value(value):
                if isinstance(value, Decimal):
                    return str(value)
                if isinstance(value, list):
                    return [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in value
                    ]
                return value

            changes[key] = {
                "old": audit_value(old_value),
                "new": audit_value(new_value),
            }

    if changes:
        for key, value in updates.items():
            setattr(line, key, value)

        db.add(
            OrderLineDetailsEvent(
                order_id=order.id,
                line_id=line.id,
                changed_fields=changes,
            )
        )
        db.commit()
        db.refresh(order)
    else:
        db.rollback()

    customer = db.get(Party, order.customer_id)
    return {
        "message": "Order item details saved." if changes else "No changes were necessary.",
        "changed_fields": list(changes.keys()),
        "order": order_to_dict(order, customer, db),
    }


@router.get("/orders/{order_id}/lines/{line_id}/details-history")
def get_order_line_details_history(
    order_id: int,
    line_id: int,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(SalesOrder).where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
    )
    if not order:
        raise HTTPException(404, "Order not found.")

    line = db.scalar(
        select(SalesOrderLine).where(
            SalesOrderLine.id == line_id,
            SalesOrderLine.order_id == order_id,
        )
    )
    if not line:
        raise HTTPException(404, "Order item not found in this order.")

    events = db.scalars(
        select(OrderLineDetailsEvent)
        .where(
            OrderLineDetailsEvent.order_id == order_id,
            OrderLineDetailsEvent.line_id == line_id,
        )
        .order_by(OrderLineDetailsEvent.changed_at.desc(), OrderLineDetailsEvent.id.desc())
    ).all()

    return [
        {
            "id": event.id,
            "changed_at": event.changed_at,
            "changed_fields": event.changed_fields,
        }
        for event in events
    ]


@router.patch("/orders/{order_id}/lines/{line_id}/progress")
def update_line_progress(
    order_id: int,
    line_id: int,
    payload: OrderProgressUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    order = db.scalar(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines))
        .where(
            SalesOrder.id == order_id,
            SalesOrder.company_id == company.id,
        )
    )
    if not order:
        raise HTTPException(404, "Order not found.")

    if order.status in ("draft", "cancelled"):
        raise HTTPException(
            409,
            "Confirm the order before recording production or dispatch.",
        )

    line = next(
        (item for item in order.lines if item.id == line_id),
        None,
    )
    if not line:
        raise HTTPException(404, "Order line not found.")

    if payload.approved_qty > payload.produced_qty:
        raise HTTPException(
            422,
            "Approved quantity cannot exceed produced quantity.",
        )

    if payload.dispatched_qty > payload.approved_qty:
        raise HTTPException(
            422,
            "Dispatched quantity cannot exceed approved quantity.",
        )

    # Progress is cumulative. Corrections will need a separate audited
    # adjustment workflow rather than silently reducing recorded quantities.
    if payload.produced_qty < line.produced_qty:
        raise HTTPException(422, "Produced quantity cannot be reduced.")
    if payload.approved_qty < line.approved_qty:
        raise HTTPException(422, "Approved quantity cannot be reduced.")
    if payload.dispatched_qty < line.dispatched_qty:
        raise HTTPException(422, "Dispatched quantity cannot be reduced.")

    line.produced_qty = payload.produced_qty
    line.approved_qty = payload.approved_qty
    line.dispatched_qty = payload.dispatched_qty

    # "completed" means production/quality target reached.
    # Dispatch remains a separate quantity and can continue afterwards.
    if all(item.approved_qty >= item.ordered_qty for item in order.lines):
        order.status = "completed"
    elif any(item.produced_qty > 0 for item in order.lines):
        order.status = "in_production"

    db.commit()

    return {
        "order_id": order.id,
        "line_id": line.id,
        "ordered_qty": line.ordered_qty,
        "produced_qty": line.produced_qty,
        "approved_qty": line.approved_qty,
        "dispatched_qty": line.dispatched_qty,
        "pending_production_qty": max(
            line.ordered_qty - line.produced_qty,
            Decimal("0"),
        ),
        "overproduction_qty": max(
            line.produced_qty - line.ordered_qty,
            Decimal("0"),
        ),
        "pending_approval_qty": max(
            line.produced_qty - line.approved_qty,
            Decimal("0"),
        ),
        "pending_dispatch_qty": max(
            line.approved_qty - line.dispatched_qty,
            Decimal("0"),
        ),
        "dispatch_complete_for_approved_qty": (
            line.dispatched_qty >= line.approved_qty
        ),
        "order_status": order.status,
    }
