from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Branch, Company, Party, Product, Warehouse, StockStage,
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    InventoryTransaction, InventoryTransactionLine,
    StockBalance, StockLedger,
)
from app.schemas.purchases import (
    SupplierCreate, SupplierOut,
    PurchaseRequestCreate, PurchaseRequestStatusUpdate,
    PurchaseOrderCreate, PurchaseOrderStatusUpdate,
    GoodsReceiptCreate, GoodsReceiptLineCreate,
)

router = APIRouter(prefix="/api/v1", tags=["Purchase Management"])


def active_company(db: Session) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.id)
    )
    if not company:
        raise HTTPException(409, "Factory company is not initialized.")
    return company


def active_branch(db: Session, company_id: int) -> Branch:
    branch = db.scalar(
        select(Branch)
        .where(
            Branch.company_id == company_id,
            Branch.is_active.is_(True),
        )
        .order_by(Branch.id)
    )
    if not branch:
        raise HTTPException(409, "No active factory branch is configured.")
    return branch


def allocate_number(db: Session, company_id: int, sequence: str, prefix: str, year: int) -> tuple[int, str]:
    db.scalar(
        select(Company)
        .where(Company.id == company_id)
        .with_for_update()
    )
    allowed = {
        "purchase_requests_id_seq",
        "purchase_orders_id_seq",
    }
    if sequence not in allowed:
        raise HTTPException(500, "Invalid document sequence.")
    document_id = db.execute(
        text(f"SELECT nextval('public.{sequence}')")
    ).scalar_one()
    return document_id, f"KDK-{prefix}-{year}-{document_id:05d}"


def request_dict(db: Session, request: PurchaseRequest):
    lines = db.scalars(
        select(PurchaseRequestLine)
        .where(PurchaseRequestLine.request_id == request.id)
        .order_by(PurchaseRequestLine.line_number)
    ).all()
    return {
        "id": request.id,
        "request_number": request.request_number,
        "branch_id": request.branch_id,
        "sales_order_id": request.sales_order_id,
        "production_plan_id": request.production_plan_id,
        "request_date": request.request_date,
        "required_date": request.required_date,
        "status": request.status,
        "notes": request.notes,
        "created_at": request.created_at,
        "lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "product_id": line.product_id,
                "requested_qty": line.requested_qty,
                "uom_code": line.uom_code,
                "notes": line.notes,
            }
            for line in lines
        ],
    }


def order_dict(db: Session, order: PurchaseOrder):
    supplier = db.get(Party, order.supplier_id)
    lines = db.scalars(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.order_id == order.id)
        .order_by(PurchaseOrderLine.line_number)
    ).all()
    return {
        "id": order.id,
        "order_number": order.order_number,
        "branch_id": order.branch_id,
        "supplier_id": order.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "request_id": order.request_id,
        "order_date": order.order_date,
        "expected_date": order.expected_date,
        "status": order.status,
        "notes": order.notes,
        "created_at": order.created_at,
        "lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "request_line_id": line.request_line_id,
                "product_id": line.product_id,
                "ordered_qty": line.ordered_qty,
                "received_qty": line.received_qty,
                "uom_code": line.uom_code,
                "unit_rate": line.unit_rate,
                "notes": line.notes,
            }
            for line in lines
        ],
    }


@router.get("/lookups/suppliers", response_model=list[SupplierOut])
def supplier_lookup(db: Session = Depends(get_db)):
    company = active_company(db)
    return db.scalars(
        select(Party)
        .where(
            Party.company_id == company.id,
            Party.party_type == "supplier",
            Party.is_active.is_(True),
        )
        .order_by(Party.name)
    ).all()


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    company = active_company(db)
    code = payload.code.strip()
    existing = db.scalar(
        select(Party).where(
            Party.company_id == company.id,
            func.lower(Party.code) == code.lower(),
        )
    )
    if existing:
        raise HTTPException(409, "A party with this code already exists.")

    supplier = Party(
        company_id=company.id,
        code=code,
        party_type="supplier",
        name=payload.name.strip(),
        contact_person=payload.contact_person,
        mobile=payload.mobile,
        email=payload.email,
        gstin=payload.gstin,
        state=payload.state,
        notes=payload.notes,
        credit_limit=Decimal("0"),
        opening_balance=Decimal("0"),
        balance_type="credit",
        is_active=True,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/lookups/purchase-products")
def purchase_product_lookup(db: Session = Depends(get_db)):
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
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "product_type": item.product_type,
            "base_uom_id": item.base_uom_id,
            "is_inventory_tracked": item.is_inventory_tracked,
        }
        for item in products
    ]


@router.get("/lookups/purchase-warehouses")
def purchase_warehouse_lookup(db: Session = Depends(get_db)):
    company = active_company(db)
    warehouses = db.scalars(
        select(Warehouse)
        .join(Branch, Warehouse.branch_id == Branch.id)
        .where(
            Branch.company_id == company.id,
            Branch.is_active.is_(True),
            Warehouse.is_active.is_(True),
        )
        .order_by(Warehouse.name)
    ).all()
    return [
        {
            "id": item.id,
            "branch_id": item.branch_id,
            "code": item.code,
            "name": item.name,
            "warehouse_type": item.warehouse_type,
        }
        for item in warehouses
    ]


@router.get("/lookups/stock-stages")
def stock_stage_lookup(db: Session = Depends(get_db)):
    company = active_company(db)
    stages = db.scalars(
        select(StockStage)
        .where(
            StockStage.company_id == company.id,
            StockStage.is_active.is_(True),
        )
        .order_by(StockStage.name)
    ).all()
    return [
        {
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "stage_type": item.stage_type,
            "tracks_rolls": item.tracks_rolls,
        }
        for item in stages
    ]


@router.get("/purchase-requests")
def list_purchase_requests(db: Session = Depends(get_db)):
    company = active_company(db)
    requests = db.scalars(
        select(PurchaseRequest)
        .where(PurchaseRequest.company_id == company.id)
        .order_by(PurchaseRequest.request_date.desc(), PurchaseRequest.id.desc())
    ).all()
    return [request_dict(db, item) for item in requests]


@router.post("/purchase-requests", status_code=201)
def create_purchase_request(
    payload: PurchaseRequestCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    branch = active_branch(db, company.id)

    for line in payload.lines:
        product = db.scalar(
            select(Product).where(
                Product.id == line.product_id,
                Product.company_id == company.id,
                Product.is_active.is_(True),
            )
        )
        if not product:
            raise HTTPException(422, f"Invalid product ID: {line.product_id}")

    request_id, number = allocate_number(
        db, company.id, "purchase_requests_id_seq",
        "PR", payload.request_date.year,
    )
    request = PurchaseRequest(
        id=request_id,
        company_id=company.id,
        branch_id=branch.id,
        sales_order_id=payload.sales_order_id,
        production_plan_id=payload.production_plan_id,
        request_number=number,
        request_date=payload.request_date,
        required_date=payload.required_date,
        status="draft",
        notes=payload.notes,
    )
    db.add(request)
    db.flush()

    for index, line in enumerate(payload.lines, start=1):
        db.add(
            PurchaseRequestLine(
                request_id=request.id,
                line_number=index,
                product_id=line.product_id,
                requested_qty=line.quantity,
                uom_code=line.uom_code,
                notes=line.notes,
            )
        )

    db.commit()
    db.refresh(request)
    return request_dict(db, request)


@router.patch("/purchase-requests/{request_id}/status")
def update_purchase_request_status(
    request_id: int,
    payload: PurchaseRequestStatusUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    request = db.scalar(
        select(PurchaseRequest)
        .where(
            PurchaseRequest.id == request_id,
            PurchaseRequest.company_id == company.id,
        )
        .with_for_update()
    )
    if not request:
        raise HTTPException(404, "Purchase request not found.")
    if request.status != "draft":
        raise HTTPException(409, "Only draft purchase requests can be updated.")
    request.status = payload.status
    db.commit()
    db.refresh(request)
    return request_dict(db, request)


@router.get("/purchase-orders")
def list_purchase_orders(db: Session = Depends(get_db)):
    company = active_company(db)
    orders = db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.company_id == company.id)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
    ).all()
    return [order_dict(db, item) for item in orders]


@router.post("/purchase-orders", status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    branch = active_branch(db, company.id)

    supplier = db.scalar(
        select(Party).where(
            Party.id == payload.supplier_id,
            Party.company_id == company.id,
            Party.party_type == "supplier",
            Party.is_active.is_(True),
        )
    )
    if not supplier:
        raise HTTPException(422, "Select a valid active supplier.")

    request = None
    if payload.request_id is not None:
        request = db.scalar(
            select(PurchaseRequest)
            .where(
                PurchaseRequest.id == payload.request_id,
                PurchaseRequest.company_id == company.id,
            )
            .with_for_update()
        )
        if not request:
            raise HTTPException(422, "Purchase request not found.")
        if request.status != "approved":
            raise HTTPException(409, "Only approved purchase requests can be converted.")

    request_lines = {}
    if request:
        request_lines = {
            line.id: line
            for line in db.scalars(
                select(PurchaseRequestLine).where(
                    PurchaseRequestLine.request_id == request.id
                )
            ).all()
        }

    for line in payload.lines:
        product = db.scalar(
            select(Product).where(
                Product.id == line.product_id,
                Product.company_id == company.id,
                Product.is_active.is_(True),
            )
        )
        if not product:
            raise HTTPException(422, f"Invalid product ID: {line.product_id}")

        if line.request_line_id is not None:
            request_line = request_lines.get(line.request_line_id)
            if not request or not request_line:
                raise HTTPException(
                    422, "A linked request line must belong to the selected purchase request."
                )
            if request_line.product_id != line.product_id:
                raise HTTPException(
                    422, "Purchase order product does not match its request line."
                )
            if line.ordered_qty > request_line.requested_qty:
                raise HTTPException(
                    422, "Ordered quantity cannot exceed the requested quantity."
                )

    order_id, number = allocate_number(
        db, company.id, "purchase_orders_id_seq",
        "PO", payload.order_date.year,
    )
    order = PurchaseOrder(
        id=order_id,
        company_id=company.id,
        branch_id=branch.id,
        supplier_id=supplier.id,
        request_id=request.id if request else None,
        order_number=number,
        order_date=payload.order_date,
        expected_date=payload.expected_date,
        status="draft",
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    for index, line in enumerate(payload.lines, start=1):
        db.add(
            PurchaseOrderLine(
                order_id=order.id,
                request_line_id=line.request_line_id,
                line_number=index,
                product_id=line.product_id,
                ordered_qty=line.ordered_qty,
                received_qty=Decimal("0"),
                uom_code=line.uom_code,
                unit_rate=line.unit_rate,
                notes=line.notes,
            )
        )

    if request:
        request.status = "converted"

    db.commit()
    db.refresh(order)
    return order_dict(db, order)


@router.patch("/purchase-orders/{order_id}/status")
def update_purchase_order_status(
    order_id: int,
    payload: PurchaseOrderStatusUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Purchase order not found.")

    if order.status != "draft":
        raise HTTPException(409, "Only draft purchase orders can be issued or cancelled.")

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order_dict(db, order)


def goods_receipt_dict(db: Session, receipt: GoodsReceipt):
    order = db.get(PurchaseOrder, receipt.order_id)
    supplier = db.get(Party, order.supplier_id) if order else None
    lines = db.scalars(
        select(GoodsReceiptLine)
        .where(GoodsReceiptLine.receipt_id == receipt.id)
        .order_by(GoodsReceiptLine.line_number)
    ).all()
    return {
        "id": receipt.id,
        "receipt_number": receipt.receipt_number,
        "order_id": receipt.order_id,
        "order_number": order.order_number if order else None,
        "supplier_name": supplier.name if supplier else None,
        "receipt_date": receipt.receipt_date,
        "supplier_reference": receipt.supplier_reference,
        "status": receipt.status,
        "inventory_transaction_id": receipt.inventory_transaction_id,
        "notes": receipt.notes,
        "created_at": receipt.created_at,
        "lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "order_line_id": line.order_line_id,
                "product_id": line.product_id,
                "warehouse_id": line.warehouse_id,
                "stock_stage_id": line.stock_stage_id,
                "received_qty": line.received_qty,
                "accepted_qty": line.accepted_qty,
                "rejected_qty": line.rejected_qty,
                "unit_cost": line.unit_cost,
                "rejection_reason": line.rejection_reason,
                "notes": line.notes,
            }
            for line in lines
        ],
    }


@router.get("/goods-receipts")
def list_goods_receipts(db: Session = Depends(get_db)):
    company = active_company(db)
    receipts = db.scalars(
        select(GoodsReceipt)
        .where(GoodsReceipt.company_id == company.id)
        .order_by(GoodsReceipt.receipt_date.desc(), GoodsReceipt.id.desc())
    ).all()
    return [goods_receipt_dict(db, item) for item in receipts]


@router.post("/goods-receipts", status_code=201)
def create_goods_receipt(
    payload: GoodsReceiptCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    order = db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == payload.order_id,
            PurchaseOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Purchase order not found.")
    if order.status not in ("issued", "partially_received"):
        raise HTTPException(409, "GRN can only be created for an issued or partially received purchase order.")

    order_lines = {
        line.id: line
        for line in db.scalars(
            select(PurchaseOrderLine)
            .where(PurchaseOrderLine.order_id == order.id)
            .with_for_update()
        ).all()
    }
    seen = set()

    for item in payload.lines:
        if item.order_line_id in seen:
            raise HTTPException(422, "Each purchase order line can appear only once in a GRN.")
        seen.add(item.order_line_id)

        order_line = order_lines.get(item.order_line_id)
        if not order_line:
            raise HTTPException(422, "A GRN line does not belong to this purchase order.")
        if item.received_qty > order_line.ordered_qty - order_line.received_qty:
            raise HTTPException(422, f"Received quantity exceeds the remaining quantity for PO line {item.order_line_id}.")

        warehouse = db.scalar(
            select(Warehouse).where(
                Warehouse.id == item.warehouse_id,
                Warehouse.branch_id == order.branch_id,
                Warehouse.is_active.is_(True),
            )
        )
        if not warehouse:
            raise HTTPException(422, "Select an active warehouse belonging to this purchase order branch.")

        stage = db.scalar(
            select(StockStage).where(
                StockStage.id == item.stock_stage_id,
                StockStage.company_id == company.id,
                StockStage.is_active.is_(True),
            )
        )
        if not stage:
            raise HTTPException(422, "Select a valid active stock stage.")

        if order_line.product_id != item.order_line_id and False:
            raise HTTPException(422, "Invalid product.")

    receipt_id, number = allocate_number(
        db, company.id, "goods_receipts_id_seq",
        "GRN", payload.receipt_date.year,
    )
    receipt = GoodsReceipt(
        id=receipt_id,
        company_id=company.id,
        branch_id=order.branch_id,
        order_id=order.id,
        receipt_number=number,
        receipt_date=payload.receipt_date,
        supplier_reference=payload.supplier_reference,
        status="draft",
        notes=payload.notes,
    )
    db.add(receipt)
    db.flush()

    for index, item in enumerate(payload.lines, start=1):
        order_line = order_lines[item.order_line_id]
        db.add(
            GoodsReceiptLine(
                receipt_id=receipt.id,
                order_line_id=order_line.id,
                line_number=index,
                product_id=order_line.product_id,
                warehouse_id=item.warehouse_id,
                stock_stage_id=item.stock_stage_id,
                received_qty=item.received_qty,
                accepted_qty=item.accepted_qty,
                rejected_qty=item.rejected_qty,
                unit_cost=item.unit_cost,
                rejection_reason=item.rejection_reason,
                notes=item.notes,
            )
        )

    db.commit()
    db.refresh(receipt)
    return goods_receipt_dict(db, receipt)


@router.get("/goods-receipts/{receipt_id}")
def get_goods_receipt(receipt_id: int, db: Session = Depends(get_db)):
    company = active_company(db)
    receipt = db.scalar(
        select(GoodsReceipt).where(
            GoodsReceipt.id == receipt_id,
            GoodsReceipt.company_id == company.id,
        )
    )
    if not receipt:
        raise HTTPException(404, "Goods receipt not found.")
    return goods_receipt_dict(db, receipt)


@router.post("/goods-receipts/{receipt_id}/post")
def post_goods_receipt(receipt_id: int, db: Session = Depends(get_db)):
    company = active_company(db)
    receipt = db.scalar(
        select(GoodsReceipt)
        .where(
            GoodsReceipt.id == receipt_id,
            GoodsReceipt.company_id == company.id,
        )
        .with_for_update()
    )
    if not receipt:
        raise HTTPException(404, "Goods receipt not found.")
    if receipt.status != "draft":
        raise HTTPException(409, "Only a draft GRN can be posted.")
    if receipt.inventory_transaction_id is not None:
        raise HTTPException(409, "This GRN has already been posted.")

    order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == receipt.order_id)
        .with_for_update()
    )
    if not order or order.status not in ("issued", "partially_received"):
        raise HTTPException(409, "The linked purchase order is not open for receipt.")

    receipt_lines = db.scalars(
        select(GoodsReceiptLine)
        .where(GoodsReceiptLine.receipt_id == receipt.id)
        .order_by(GoodsReceiptLine.line_number)
        .with_for_update()
    ).all()
    order_lines = {
        line.id: line
        for line in db.scalars(
            select(PurchaseOrderLine)
            .where(PurchaseOrderLine.order_id == order.id)
            .with_for_update()
        ).all()
    }

    # Validate every line before changing inventory.
    for item in receipt_lines:
        order_line = order_lines.get(item.order_line_id)
        if not order_line or order_line.product_id != item.product_id:
            raise HTTPException(409, "A GRN line no longer matches its purchase order line.")
        if item.received_qty > order_line.ordered_qty - order_line.received_qty:
            raise HTTPException(409, f"Posting would exceed ordered quantity for PO line {order_line.id}.")

    transaction = InventoryTransaction(
        company_id=company.id,
        branch_id=receipt.branch_id,
        transaction_number=f"KDK-INV-{receipt.receipt_number}",
        transaction_type="receipt",
        transaction_date=receipt.receipt_date,
        status="posted",
        source_type="goods_receipt",
        source_id=receipt.id,
        idempotency_key=f"purchase-grn:{receipt.id}",
        reference_number=receipt.receipt_number,
        notes=receipt.notes,
        posted_at=datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.flush()

    total_received = {}
    for item in receipt_lines:
        order_line = order_lines[item.order_line_id]
        order_line.received_qty += item.received_qty
        total_received[order_line.id] = order_line.received_qty

    for index, item in enumerate(receipt_lines, start=1):
        if item.accepted_qty <= 0:
            continue

        # Serialize updates to the same stock dimension, including first receipt.
        lock_key = (
            f"{company.id}:{item.product_id}:"
            f"{item.warehouse_id}:{item.stock_stage_id}"
        )
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": lock_key},
        )

        balance = db.scalar(
            select(StockBalance)
            .where(
                StockBalance.company_id == company.id,
                StockBalance.product_id == item.product_id,
                StockBalance.warehouse_id == item.warehouse_id,
                StockBalance.stock_stage_id == item.stock_stage_id,
            )
            .with_for_update()
        )
        if balance is None:
            balance = StockBalance(
                company_id=company.id,
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                stock_stage_id=item.stock_stage_id,
                quantity_on_hand=Decimal("0"),
                inventory_value=Decimal("0"),
                average_unit_cost=Decimal("0"),
            )
            db.add(balance)
            db.flush()

        old_qty = Decimal(balance.quantity_on_hand)
        old_value = Decimal(balance.inventory_value)
        accepted = Decimal(item.accepted_qty)
        unit_cost = Decimal(item.unit_cost)
        value_in = (accepted * unit_cost).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        new_qty = old_qty + accepted
        new_value = old_value + value_in
        average_cost = (new_value / new_qty).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        transaction_line = InventoryTransactionLine(
            transaction_id=transaction.id,
            line_number=index,
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            stock_stage_id=item.stock_stage_id,
            direction="in",
            quantity=accepted,
            unit_cost=unit_cost,
            line_value=value_in,
            notes=f"GRN {receipt.receipt_number}",
        )
        db.add(transaction_line)
        db.flush()

        balance.quantity_on_hand = new_qty
        balance.inventory_value = new_value
        balance.average_unit_cost = average_cost

        db.add(
            StockLedger(
                company_id=company.id,
                transaction_id=transaction.id,
                transaction_line_id=transaction_line.id,
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                stock_stage_id=item.stock_stage_id,
                quantity_in=accepted,
                quantity_out=Decimal("0"),
                balance_after=new_qty,
                unit_cost=unit_cost,
                value_in=value_in,
                value_out=Decimal("0"),
                value_balance_after=new_value,
            )
        )

    db.flush()
    all_order_lines = list(order_lines.values())
    if all(line.received_qty >= line.ordered_qty for line in all_order_lines):
        order.status = "received"
    elif any(line.received_qty > 0 for line in all_order_lines):
        order.status = "partially_received"

    receipt.status = "posted"
    receipt.inventory_transaction_id = transaction.id
    db.commit()
    db.refresh(receipt)

    return {
        "message": "Goods receipt posted successfully.",
        "receipt": goods_receipt_dict(db, receipt),
        "inventory_transaction_id": transaction.id,
        "purchase_order_status": order.status,
    }



# Direct supplier bill entry. This records the purchase document only;
# inventory is changed exclusively through the accepted GRN workflow.
from datetime import date
from pydantic import BaseModel, Field, field_validator


class PurchaseEntryLinePayload(BaseModel):
    category: str = Field(default="Other", max_length=60)
    material_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    rate: Decimal = Field(ge=0, max_digits=16, decimal_places=4)
    amount: Decimal | None = None
    product_id: int | None = Field(default=None, gt=0)


class PurchaseEntryPayload(BaseModel):
    purchase_number: str = Field(min_length=1, max_length=60)
    purchase_date: date
    supplier_id: int | None = Field(default=None, gt=0)
    supplier_name: str = Field(min_length=1, max_length=200)
    mobile: str | None = Field(default=None, max_length=30)
    gstin: str | None = Field(default=None, max_length=20)
    supplier_bill_number: str | None = Field(default=None, max_length=100)
    warehouse_id: int | None = Field(default=None, gt=0)
    freight: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16, decimal_places=2)
    other_charges: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16, decimal_places=2)
    payment_status: str = Field(default="unpaid", max_length=30)
    payment_method: str | None = Field(default=None, max_length=50)
    remarks: str | None = None
    lines: list[PurchaseEntryLinePayload] = Field(min_length=1)

    @field_validator("purchase_number", "supplier_name")
    @classmethod
    def trim_required_entry_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


def _purchase_entry_dict(db: Session, entry_id: int, company_id: int):
    entry = db.execute(
        text("""
            SELECT id, purchase_number, purchase_date, supplier_id,
                   supplier_name, mobile, gstin, supplier_bill_number,
                   warehouse_id, freight, other_charges, payment_status,
                   payment_method, remarks, subtotal, grand_total
            FROM purchase_entries
            WHERE id = :id AND company_id = :company_id
        """),
        {"id": entry_id, "company_id": company_id},
    ).mappings().first()

    if not entry:
        raise HTTPException(404, "Purchase entry not found.")

    lines = db.execute(
        text("""
            SELECT id, category, material_name, description, quantity,
                   unit, rate, amount, product_id
            FROM purchase_entry_lines
            WHERE purchase_entry_id = :entry_id
            ORDER BY line_number
        """),
        {"entry_id": entry_id},
    ).mappings().all()

    return {**dict(entry), "lines": [dict(line) for line in lines]}


def _save_purchase_entry_lines(db: Session, entry_id: int, lines):
    subtotal = Decimal("0.00")

    for index, line in enumerate(lines, start=1):
        amount = (Decimal(line.quantity) * Decimal(line.rate)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        subtotal += amount

        db.execute(
            text("""
                INSERT INTO purchase_entry_lines
                (purchase_entry_id, line_number, category, material_name,
                 description, quantity, unit, rate, amount, product_id)
                VALUES
                (:entry_id, :line_number, :category, :material_name,
                 :description, :quantity, :unit, :rate, :amount, :product_id)
            """),
            {
                "entry_id": entry_id,
                "line_number": index,
                "category": line.category.strip() or "Other",
                "material_name": line.material_name.strip(),
                "description": line.description,
                "quantity": line.quantity,
                "unit": line.unit.strip(),
                "rate": line.rate,
                "amount": amount,
                "product_id": line.product_id,
            },
        )

    return subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _purchase_entry_values(payload):
    return {
        "purchase_number": payload.purchase_number.strip(),
        "purchase_date": payload.purchase_date,
        "supplier_id": payload.supplier_id,
        "supplier_name": payload.supplier_name.strip(),
        "mobile": payload.mobile,
        "gstin": payload.gstin,
        "supplier_bill_number": payload.supplier_bill_number,
        "warehouse_id": payload.warehouse_id,
        "freight": payload.freight,
        "other_charges": payload.other_charges,
        "payment_status": payload.payment_status,
        "payment_method": payload.payment_method,
        "remarks": payload.remarks,
    }


@router.get("/purchase-entries")
def list_purchase_entries(db: Session = Depends(get_db)):
    company = active_company(db)
    rows = db.execute(
        text("""
            SELECT id FROM purchase_entries
            WHERE company_id = :company_id
            ORDER BY purchase_date DESC, id DESC
        """),
        {"company_id": company.id},
    ).mappings().all()

    return [
        _purchase_entry_dict(db, row["id"], company.id)
        for row in rows
    ]


@router.post("/purchase-entries", status_code=201)
def create_purchase_entry(
    payload: PurchaseEntryPayload,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    branch = active_branch(db, company.id)
    values = _purchase_entry_values(payload)

    try:
        subtotal = sum(
            (
                Decimal(line.quantity) * Decimal(line.rate)
                for line in payload.lines
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        grand_total = (
            subtotal + payload.freight + payload.other_charges
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        entry_id = db.execute(
            text("""
                INSERT INTO purchase_entries
                (company_id, branch_id, purchase_number, purchase_date,
                 supplier_id, supplier_name, mobile, gstin,
                 supplier_bill_number, warehouse_id, freight, other_charges,
                 payment_status, payment_method, remarks, subtotal, grand_total)
                VALUES
                (:company_id, :branch_id, :purchase_number, :purchase_date,
                 :supplier_id, :supplier_name, :mobile, :gstin,
                 :supplier_bill_number, :warehouse_id, :freight, :other_charges,
                 :payment_status, :payment_method, :remarks, :subtotal, :grand_total)
                RETURNING id
            """),
            {
                **values,
                "company_id": company.id,
                "branch_id": branch.id,
                "subtotal": subtotal,
                "grand_total": grand_total,
            },
        ).scalar_one()

        _save_purchase_entry_lines(db, entry_id, payload.lines)
        db.commit()
        return _purchase_entry_dict(db, entry_id, company.id)

    except Exception:
        db.rollback()
        raise


@router.put("/purchase-entries/{entry_id}")
def update_purchase_entry(
    entry_id: int,
    payload: PurchaseEntryPayload,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    values = _purchase_entry_values(payload)

    existing = db.execute(
        text("""
            SELECT id FROM purchase_entries
            WHERE id = :id AND company_id = :company_id
            FOR UPDATE
        """),
        {"id": entry_id, "company_id": company.id},
    ).first()

    if not existing:
        raise HTTPException(404, "Purchase entry not found.")

    subtotal = sum(
        (
            Decimal(line.quantity) * Decimal(line.rate)
            for line in payload.lines
        ),
        Decimal("0"),
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    grand_total = (
        subtotal + payload.freight + payload.other_charges
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    try:
        db.execute(
            text("""
                UPDATE purchase_entries SET
                    purchase_number = :purchase_number,
                    purchase_date = :purchase_date,
                    supplier_id = :supplier_id,
                    supplier_name = :supplier_name,
                    mobile = :mobile,
                    gstin = :gstin,
                    supplier_bill_number = :supplier_bill_number,
                    warehouse_id = :warehouse_id,
                    freight = :freight,
                    other_charges = :other_charges,
                    payment_status = :payment_status,
                    payment_method = :payment_method,
                    remarks = :remarks,
                    subtotal = :subtotal,
                    grand_total = :grand_total,
                    updated_at = now()
                WHERE id = :id AND company_id = :company_id
            """),
            {
                **values,
                "subtotal": subtotal,
                "grand_total": grand_total,
                "id": entry_id,
                "company_id": company.id,
            },
        )

        db.execute(
            text("DELETE FROM purchase_entry_lines WHERE purchase_entry_id = :id"),
            {"id": entry_id},
        )
        _save_purchase_entry_lines(db, entry_id, payload.lines)
        db.commit()
        return _purchase_entry_dict(db, entry_id, company.id)

    except Exception:
        db.rollback()
        raise


@router.delete("/purchase-entries/{entry_id}")
def delete_purchase_entry(
    entry_id: int,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    try:
        existing = db.execute(
            text("""
                SELECT id FROM purchase_entries
                WHERE id = :id AND company_id = :company_id
                FOR UPDATE
            """),
            {"id": entry_id, "company_id": company.id},
        ).first()

        if not existing:
            raise HTTPException(404, "Purchase entry not found.")

        # Delete only the purchase's detail rows and header.
        # Inventory and stock ledger are deliberately untouched.
        db.execute(
            text("DELETE FROM purchase_entry_lines WHERE purchase_entry_id = :id"),
            {"id": entry_id},
        )
        db.execute(
            text("""
                DELETE FROM purchase_entries
                WHERE id = :id AND company_id = :company_id
            """),
            {"id": entry_id, "company_id": company.id},
        )
        db.commit()
        return {"message": "Purchase entry deleted successfully."}

    except Exception:
        db.rollback()
        raise
