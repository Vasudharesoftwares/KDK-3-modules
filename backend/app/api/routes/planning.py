from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import (
    Branch,
    Company,
    Machine,
    Party,
    PlanningAllocation,
    PlanningEvent,
    PlanningMachine,
    PlanningWorker,
    ProductionPlan,
    SalesOrder,
    SalesOrderLine,
    Shift,
    Worker,
)
from app.schemas.planning import (
    PlanningActualUpdate,
    PlanningAllocationCreate,
    PlanningStatusUpdate,
    ProductionPlanCreate,
    ProductionPlanUpdate,
)

router = APIRouter(prefix="/api/v1/planning", tags=["Planning & Scheduling"])
LOCAL_TZ = ZoneInfo(getattr(settings, "TIMEZONE", "Asia/Kolkata"))
ACTIVE_PLAN_STATUSES = ("scheduled", "in_progress")
ALL_NON_CANCELLED_PLAN_STATUSES = (
    "draft", "scheduled", "in_progress", "completed"
)


def active_company(db: Session) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.id)
    )
    if not company:
        raise HTTPException(409, "Factory company is not initialized.")
    return company


def plan_or_404(db: Session, company_id: int, plan_id: int) -> ProductionPlan:
    plan = db.scalar(
        select(ProductionPlan).where(
            ProductionPlan.id == plan_id,
            ProductionPlan.company_id == company_id,
        )
    )
    if not plan:
        raise HTTPException(404, "Production plan not found.")
    return plan


def event(
    db: Session,
    plan_id: int,
    event_type: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
    reason: str | None = None,
) -> None:
    db.add(PlanningEvent(
        plan_id=plan_id,
        event_type=event_type,
        before_data=before_data,
        after_data=after_data,
        reason=reason,
    ))


def plan_dict(plan: ProductionPlan, db: Session) -> dict:
    order = db.get(SalesOrder, plan.sales_order_id)
    line = db.get(SalesOrderLine, plan.sales_order_line_id)
    allocations = db.scalars(
        select(PlanningAllocation)
        .where(PlanningAllocation.plan_id == plan.id)
        .order_by(PlanningAllocation.starts_at, PlanningAllocation.id)
    ).all()

    allocation_rows = []
    for allocation in allocations:
        machine = db.get(Machine, allocation.machine_id) if allocation.machine_id else None
        shift = db.get(Shift, allocation.shift_id) if allocation.shift_id else None
        worker = db.get(Worker, allocation.worker_id) if allocation.worker_id else None
        allocation_rows.append({
            "id": allocation.id,
            "machine_id": allocation.machine_id,
            "machine_code": machine.code if machine else None,
            "machine_name": allocation.machine_name_snapshot or (machine.name if machine else None),
            "shift_id": allocation.shift_id,
            "shift_name": shift.name if shift else None,
            "worker_id": allocation.worker_id,
            "worker_name": allocation.worker_name_snapshot or (worker.full_name if worker else None),
            "manual_entry": allocation.manual_entry,
            "work_date": allocation.work_date,
            "starts_at": allocation.starts_at,
            "ends_at": allocation.ends_at,
        })

    return {
        "id": plan.id,
        "plan_number": plan.plan_number,
        "company_id": plan.company_id,
        "branch_id": plan.branch_id,
        "sales_order_id": plan.sales_order_id,
        "order_number": order.order_number if order else None,
        "order_status": order.status if order else None,
        "sales_order_line_id": plan.sales_order_line_id,
        "item_description": line.description if line else None,
        "ordered_qty": line.ordered_qty if line else None,
        "order_produced_qty": line.produced_qty if line else None,
        "planned_qty": plan.planned_qty,
        "actual_qty": plan.actual_qty,
        "uom_code": plan.uom_code,
        "planned_start_date": plan.planned_start_date,
        "target_end_date": plan.target_end_date,
        "status": plan.status,
        "notes": plan.notes,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "allocations": allocation_rows,
    }


@router.get("/dashboard")
def planning_dashboard(db: Session = Depends(get_db)):
    company = active_company(db)
    counts = {}
    for status in ("draft", "scheduled", "in_progress", "completed", "cancelled"):
        counts[status] = db.scalar(
            select(func.count(ProductionPlan.id)).where(
                ProductionPlan.company_id == company.id,
                ProductionPlan.status == status,
            )
        ) or 0

    totals = db.execute(
        select(
            func.coalesce(func.sum(ProductionPlan.planned_qty), 0),
            func.coalesce(func.sum(ProductionPlan.actual_qty), 0),
        ).where(
            ProductionPlan.company_id == company.id,
            ProductionPlan.status != "cancelled",
        )
    ).one()

    return {
        "counts": counts,
        "planned_qty": totals[0],
        "actual_qty": totals[1],
        "active_machines": db.scalar(
            select(func.count(Machine.id)).where(
                Machine.company_id == company.id,
                Machine.is_active.is_(True),
            )
        ) or 0,
        "active_shifts": db.scalar(
            select(func.count(Shift.id)).where(
                Shift.company_id == company.id,
                Shift.is_active.is_(True),
            )
        ) or 0,
        "active_workers": db.scalar(
            select(func.count(Worker.id)).where(
                Worker.company_id == company.id,
                Worker.is_active.is_(True),
            )
        ) or 0,
    }


@router.get("/lookups")
def planning_lookups(db: Session = Depends(get_db)):
    company = active_company(db)

    orders = db.execute(
        select(SalesOrder, Party)
        .join(Party, Party.id == SalesOrder.customer_id)
        .where(
            SalesOrder.company_id == company.id,
            SalesOrder.status.in_(("confirmed", "in_production")),
        )
        .order_by(SalesOrder.delivery_date, SalesOrder.order_number)
    ).all()

    eligible_orders = []
    for order, customer in orders:
        lines = db.scalars(
            select(SalesOrderLine)
            .where(SalesOrderLine.order_id == order.id)
            .order_by(SalesOrderLine.line_number)
        ).all()
        eligible_lines = []
        for line in lines:
            planned = db.scalar(
                select(func.coalesce(func.sum(ProductionPlan.planned_qty), 0))
                .where(
                    ProductionPlan.sales_order_line_id == line.id,
                    ProductionPlan.status.in_(ALL_NON_CANCELLED_PLAN_STATUSES),
                )
            ) or Decimal("0")
            remaining = max(
                Decimal("0"),
                Decimal(line.ordered_qty) - Decimal(line.produced_qty) - Decimal(planned),
            )
            if remaining > 0:
                eligible_lines.append({
                    "id": line.id,
                    "line_number": line.line_number,
                    "description": line.description,
                    "ordered_qty": line.ordered_qty,
                    "produced_qty": line.produced_qty,
                    "already_planned_qty": planned,
                    "available_to_plan_qty": remaining,
                    "uom_code": line.uom_code,
                })
        if eligible_lines:
            eligible_orders.append({
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": customer.name,
                "order_date": order.order_date,
                "delivery_date": order.delivery_date,
                "priority": order.priority,
                "status": order.status,
                "lines": eligible_lines,
            })

    machines = db.scalars(
        select(Machine)
        .join(Branch, Branch.id == Machine.branch_id)
        .where(
            Machine.company_id == company.id,
            Machine.is_active.is_(True),
            Branch.is_active.is_(True),
        )
        .order_by(Machine.name)
    ).all()

    shifts = db.scalars(
        select(Shift)
        .where(
            Shift.company_id == company.id,
            Shift.is_active.is_(True),
        )
        .order_by(Shift.sequence_no, Shift.id)
    ).all()

    workers = db.scalars(
        select(Worker)
        .where(
            Worker.company_id == company.id,
            Worker.is_active.is_(True),
        )
        .order_by(Worker.full_name)
    ).all()

    saved_machines = db.scalars(
        select(PlanningMachine).where(
            PlanningMachine.company_id == company.id,
            PlanningMachine.is_active.is_(True),
        ).order_by(PlanningMachine.name)
    ).all()
    saved_workers = db.scalars(
        select(PlanningWorker).where(
            PlanningWorker.company_id == company.id,
            PlanningWorker.is_active.is_(True),
        ).order_by(PlanningWorker.name)
    ).all()

    return {
        "saved_machines": [
            {"id": item.id, "name": item.name, "branch_id": item.branch_id}
            for item in saved_machines
        ],
        "saved_workers": [
            {"id": item.id, "name": item.name, "branch_id": item.branch_id}
            for item in saved_workers
        ],
        "eligible_orders": eligible_orders,
        "machines": [
            {"id": m.id, "code": m.code, "name": m.name,
             "machine_type_id": m.machine_type_id, "branch_id": m.branch_id}
            for m in machines
        ],
        "shifts": [
            {"id": s.id, "code": s.code, "name": s.name,
             "start_time": s.start_time, "end_time": s.end_time,
             "sequence_no": s.sequence_no}
            for s in shifts
        ],
        "workers": [
            {"id": w.id, "worker_code": w.worker_code,
             "full_name": w.full_name, "worker_type": w.worker_type}
            for w in workers
        ],
        "timezone": str(LOCAL_TZ),
    }


@router.get("/plans")
def list_plans(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    query = select(ProductionPlan).where(
        ProductionPlan.company_id == company.id
    )
    if status:
        allowed = {
            "draft", "scheduled", "in_progress", "completed", "cancelled"
        }
        if status not in allowed:
            raise HTTPException(422, "Invalid plan status filter.")
        query = query.where(ProductionPlan.status == status)

    plans = db.scalars(
        query.order_by(
            ProductionPlan.planned_start_date.desc(),
            ProductionPlan.id.desc(),
        )
    ).all()
    return [plan_dict(plan, db) for plan in plans]


@router.post("/plans", status_code=201)
def create_plan(
    payload: ProductionPlanCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    # Lock company row to serialize plan-number allocation and line planning.
    db.scalar(
        select(Company)
        .where(Company.id == company.id)
        .with_for_update()
    )

    line = db.scalar(
        select(SalesOrderLine)
        .where(SalesOrderLine.id == payload.sales_order_line_id)
        .with_for_update()
    )
    if not line:
        raise HTTPException(404, "Sales order item not found.")

    order = db.get(SalesOrder, line.order_id)
    if not order or order.company_id != company.id:
        raise HTTPException(404, "Sales order item not found for this company.")
    if order.status not in ("confirmed", "in_production"):
        raise HTTPException(
            409, "Only confirmed or in-production sales orders can be planned."
        )

    already_planned = db.scalar(
        select(func.coalesce(func.sum(ProductionPlan.planned_qty), 0))
        .where(
            ProductionPlan.sales_order_line_id == line.id,
            ProductionPlan.status.in_(ALL_NON_CANCELLED_PLAN_STATUSES),
        )
    ) or Decimal("0")

    remaining = (
        Decimal(line.ordered_qty)
        - Decimal(line.produced_qty)
        - Decimal(already_planned)
    )
    if payload.planned_qty > remaining:
        raise HTTPException(
            422,
            f"Plan quantity exceeds available quantity ({max(Decimal('0'), remaining)} {line.uom_code}).",
        )

    next_number = (db.scalar(
        select(func.coalesce(func.max(ProductionPlan.id), 0))
    ) or 0) + 1
    plan_number = f"KDK-PP-{payload.planned_start_date.year}-{next_number:05d}"

    plan = ProductionPlan(
        company_id=company.id,
        branch_id=order.branch_id,
        sales_order_id=order.id,
        sales_order_line_id=line.id,
        plan_number=plan_number,
        planned_qty=payload.planned_qty,
        actual_qty=Decimal("0"),
        uom_code=line.uom_code,
        planned_start_date=payload.planned_start_date,
        target_end_date=payload.target_end_date,
        status="draft",
        notes=payload.notes,
    )
    db.add(plan)
    db.flush()

    event(
        db, plan.id, "plan_created",
        after_data={
            "plan_number": plan.plan_number,
            "sales_order_id": order.id,
            "sales_order_line_id": line.id,
            "planned_qty": str(plan.planned_qty),
            "uom_code": plan.uom_code,
            "planned_start_date": str(plan.planned_start_date),
            "target_end_date": str(plan.target_end_date) if plan.target_end_date else None,
        },
    )
    db.commit()
    db.refresh(plan)
    return plan_dict(plan, db)






@router.patch("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    payload: ProductionPlanUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    plan = db.scalar(
        select(ProductionPlan)
        .where(
            ProductionPlan.id == plan_id,
            ProductionPlan.company_id == company.id,
        )
        .with_for_update()
    )
    if not plan:
        raise HTTPException(404, "Production plan not found.")

    if plan.status in ("completed", "cancelled"):
        raise HTTPException(409, "Completed or cancelled plans cannot be edited.")

    new_qty = Decimal(payload.planned_qty)
    old_line_id = plan.sales_order_line_id
    new_line_id = payload.sales_order_line_id

    if new_qty < Decimal(plan.actual_qty):
        raise HTTPException(
            422,
            "Planned quantity cannot be lower than already recorded actual output.",
        )

    line = db.scalar(
        select(SalesOrderLine)
        .where(SalesOrderLine.id == new_line_id)
        .with_for_update()
    )
    if not line:
        raise HTTPException(404, "Sales order line not found.")

    order = db.scalar(
        select(SalesOrder)
        .where(
            SalesOrder.id == line.order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Sales order not found.")

    if order.status not in ("confirmed", "in_production"):
        raise HTTPException(
            409,
            "The selected sales order must be confirmed or in production.",
        )

    if Decimal(plan.actual_qty) > 0 and new_line_id != old_line_id:
        raise HTTPException(
            409,
            "This plan has recorded production. Its sales order line cannot be changed.",
        )

    if order.branch_id != plan.branch_id:
        raise HTTPException(
            409,
            "A production plan can only be moved to an order line in the same branch.",
        )

    already_planned = db.scalar(
        select(func.coalesce(func.sum(ProductionPlan.planned_qty), 0)).where(
            ProductionPlan.sales_order_line_id == new_line_id,
            ProductionPlan.id != plan.id,
            ProductionPlan.status != "cancelled",
        )
    ) or Decimal("0")

    remaining = Decimal(line.ordered_qty) - Decimal(line.produced_qty) - Decimal(already_planned)

    if new_qty > remaining:
        raise HTTPException(
            422,
            f"Plan quantity exceeds available quantity ({max(Decimal('0'), remaining)} {line.uom_code}).",
        )

    before = {
        "sales_order_id": plan.sales_order_id,
        "sales_order_line_id": plan.sales_order_line_id,
        "planned_qty": str(plan.planned_qty),
        "planned_start_date": str(plan.planned_start_date),
        "target_end_date": str(plan.target_end_date) if plan.target_end_date else None,
        "notes": plan.notes,
    }

    plan.sales_order_id = order.id
    plan.sales_order_line_id = line.id
    plan.planned_qty = new_qty
    plan.uom_code = line.uom_code
    plan.planned_start_date = payload.planned_start_date
    plan.target_end_date = payload.target_end_date
    plan.notes = payload.notes

    after = {
        "sales_order_id": plan.sales_order_id,
        "sales_order_line_id": plan.sales_order_line_id,
        "planned_qty": str(plan.planned_qty),
        "planned_start_date": str(plan.planned_start_date),
        "target_end_date": str(plan.target_end_date) if plan.target_end_date else None,
        "notes": plan.notes,
    }

    event(
        db,
        plan.id,
        "plan_details_updated",
        before_data=before,
        after_data=after,
    )

    db.commit()
    db.refresh(plan)
    return plan_dict(plan, db)


@router.post("/plans/{plan_id}/allocations", status_code=201)
def add_allocation(
    plan_id: int,
    payload: PlanningAllocationCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    plan = db.scalar(
        select(ProductionPlan)
        .where(
            ProductionPlan.id == plan_id,
            ProductionPlan.company_id == company.id,
        )
        .with_for_update()
    )
    if not plan:
        raise HTTPException(404, "Production plan not found.")
    if plan.status not in ("draft", "scheduled", "in_progress"):
        raise HTTPException(409, "Allocations cannot be added to this plan.")

    machine_name = payload.machine_name.strip()
    worker_name = payload.worker_name.strip()
    machine_normalized = " ".join(machine_name.casefold().split())
    worker_normalized = " ".join(worker_name.casefold().split())

    if not machine_normalized or not worker_normalized:
        raise HTTPException(422, "Machine and worker names are required.")

    starts_at = payload.starts_at.astimezone(ZoneInfo("UTC"))
    ends_at = payload.ends_at.astimezone(ZoneInfo("UTC"))
    work_date = payload.starts_at.astimezone(LOCAL_TZ).date()

    # Reuse names within this company and branch; otherwise save them for future suggestions.
    machine = db.scalar(
        select(PlanningMachine).where(
            PlanningMachine.company_id == company.id,
            PlanningMachine.branch_id == plan.branch_id,
            PlanningMachine.normalized_name == machine_normalized,
        ).with_for_update()
    )
    if machine is None:
        machine = PlanningMachine(
            company_id=company.id,
            branch_id=plan.branch_id,
            name=machine_name,
            normalized_name=machine_normalized,
            is_active=True,
        )
        db.add(machine)
        db.flush()
    elif not machine.is_active:
        machine.is_active = True

    worker = db.scalar(
        select(PlanningWorker).where(
            PlanningWorker.company_id == company.id,
            PlanningWorker.branch_id == plan.branch_id,
            PlanningWorker.normalized_name == worker_normalized,
        ).with_for_update()
    )
    if worker is None:
        worker = PlanningWorker(
            company_id=company.id,
            branch_id=plan.branch_id,
            name=worker_name,
            normalized_name=worker_normalized,
            is_active=True,
        )
        db.add(worker)
        db.flush()
    elif not worker.is_active:
        worker.is_active = True

    overlap_base = (
        select(PlanningAllocation)
        .join(ProductionPlan, ProductionPlan.id == PlanningAllocation.plan_id)
        .where(
            ProductionPlan.company_id == company.id,
            ProductionPlan.branch_id == plan.branch_id,
            ProductionPlan.status.in_(ACTIVE_PLAN_STATUSES),
            PlanningAllocation.manual_entry.is_(True),
            PlanningAllocation.starts_at < ends_at,
            PlanningAllocation.ends_at > starts_at,
        )
    )

    overlapping_allocations = db.scalars(overlap_base).all()

    def normalize_name(value: str | None) -> str:
        return " ".join((value or "").casefold().split())

    machine_conflict = any(
        normalize_name(row.machine_name_snapshot) == machine_normalized
        for row in overlapping_allocations
    )
    if machine_conflict:
        db.rollback()
        raise HTTPException(
            409,
            f"Machine '{machine_name}' is already allocated during that time.",
        )

    worker_conflict = any(
        normalize_name(row.worker_name_snapshot) == worker_normalized
        for row in overlapping_allocations
    )
    if worker_conflict:
        db.rollback()
        raise HTTPException(
            409,
            f"Worker '{worker_name}' is already allocated during that time.",
        )

    allocation = PlanningAllocation(
        plan_id=plan.id,
        machine_id=None,
        shift_id=None,
        worker_id=None,
        planning_machine_id=machine.id,
        planning_worker_id=worker.id,
        machine_name_snapshot=machine.name,
        worker_name_snapshot=worker.name,
        manual_entry=True,
        work_date=work_date,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(allocation)

    if plan.status == "draft":
        plan.status = "scheduled"

    event(
        db, plan.id, "allocation_added",
        after_data={
            "machine_name": machine.name,
            "worker_name": worker.name,
            "work_date": str(work_date),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "timezone": str(LOCAL_TZ),
            "manual_entry": True,
        },
    )
    db.commit()
    db.refresh(allocation)

    return {
        "id": allocation.id,
        "plan_id": plan.id,
        "machine_id": None,
        "machine_name": allocation.machine_name_snapshot,
        "shift_id": None,
        "shift_name": None,
        "worker_id": None,
        "worker_name": allocation.worker_name_snapshot,
        "manual_entry": True,
        "work_date": allocation.work_date,
        "starts_at": allocation.starts_at,
        "ends_at": allocation.ends_at,
        "plan_status": plan.status,
    }


@router.patch("/plans/{plan_id}/status")
def update_plan_status(
    plan_id: int,
    payload: PlanningStatusUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    plan = db.scalar(
        select(ProductionPlan)
        .where(
            ProductionPlan.id == plan_id,
            ProductionPlan.company_id == company.id,
        )
        .with_for_update()
    )
    if not plan:
        raise HTTPException(404, "Production plan not found.")

    old_status = plan.status
    new_status = payload.status
    if old_status == new_status:
        return {"id": plan.id, "status": plan.status}

    if old_status == "cancelled" or old_status == "completed":
        raise HTTPException(409, "Completed or cancelled plans cannot be reopened.")

    if new_status == "scheduled":
        allocation_count = db.scalar(
            select(func.count(PlanningAllocation.id)).where(
                PlanningAllocation.plan_id == plan.id
            )
        ) or 0
        if not allocation_count:
            raise HTTPException(409, "Save at least one machine and worker assignment first.")

    if new_status == "in_progress" and old_status not in ("scheduled", "in_progress"):
        raise HTTPException(409, "Schedule the plan before starting production.")

    if new_status == "completed":
        if plan.actual_qty <= 0:
            raise HTTPException(409, "Record actual output before completing the plan.")

    plan.status = new_status
    event(
        db, plan.id, "status_changed",
        before_data={"status": old_status},
        after_data={"status": new_status},
        reason=payload.reason,
    )
    db.commit()
    return {"id": plan.id, "status": plan.status}


@router.patch("/plans/{plan_id}/actual")
def update_plan_actual(
    plan_id: int,
    payload: PlanningActualUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    plan = db.scalar(
        select(ProductionPlan)
        .where(
            ProductionPlan.id == plan_id,
            ProductionPlan.company_id == company.id,
        )
        .with_for_update()
    )
    if not plan:
        raise HTTPException(404, "Production plan not found.")

    if plan.status in ("completed", "cancelled"):
        raise HTTPException(409, "Actual output cannot be changed on a closed plan.")

    old_qty = Decimal(plan.actual_qty)
    new_qty = Decimal(payload.actual_qty)

    if new_qty < old_qty:
        raise HTTPException(
            422,
            "Recorded actual output cannot be reduced. Use an audited production adjustment workflow.",
        )

    if new_qty > Decimal(plan.planned_qty):
        raise HTTPException(
            422,
            f"Actual output cannot exceed this plan's planned quantity ({plan.planned_qty} {plan.uom_code}).",
        )

    # Lock the order line so concurrent plans for the same line
    # cannot add production against the same remaining quantity.
    line = db.scalar(
        select(SalesOrderLine)
        .where(
            SalesOrderLine.id == plan.sales_order_line_id,
        )
        .with_for_update()
    )
    if not line or line.order_id != plan.sales_order_id:
        raise HTTPException(409, "The sales order line linked to this plan is unavailable.")

    order = db.scalar(
        select(SalesOrder)
        .where(
            SalesOrder.id == plan.sales_order_id,
            SalesOrder.company_id == company.id,
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(404, "Linked sales order not found.")

    if order.status not in ("confirmed", "in_production"):
        raise HTTPException(
            409,
            "Production output can only be recorded against a confirmed or in-production order.",
        )

    # Only the change in this plan's actual output is added.
    # Historical plan quantities are deliberately not backfilled.
    delta = new_qty - old_qty
    old_order_qty = Decimal(line.produced_qty)
    new_order_qty = old_order_qty + delta

    if new_order_qty > Decimal(line.ordered_qty):
        remaining = max(
            Decimal("0"),
            Decimal(line.ordered_qty) - old_order_qty,
        )
        raise HTTPException(
            422,
            f"Production output exceeds the sales order's remaining quantity ({remaining} {line.uom_code}).",
        )

    plan.actual_qty = new_qty
    line.produced_qty = new_order_qty

    if plan.status == "scheduled" and new_qty > 0:
        plan.status = "in_progress"

    if order.status == "confirmed" and new_order_qty > 0:
        order.status = "in_production"

    event(
        db,
        plan.id,
        "actual_output_updated",
        before_data={
            "actual_qty": str(old_qty),
            "order_produced_qty": str(old_order_qty),
        },
        after_data={
            "actual_qty": str(new_qty),
            "order_produced_qty": str(new_order_qty),
            "production_delta": str(delta),
        },
        reason=payload.reason,
    )

    # Plan and order progress commit together.
    # Quality approval and inventory posting remain separate.
    db.commit()
    db.refresh(plan)
    db.refresh(line)
    db.refresh(order)

    return {
        "id": plan.id,
        "plan_number": plan.plan_number,
        "planned_qty": plan.planned_qty,
        "actual_qty": plan.actual_qty,
        "status": plan.status,
        "production_delta": delta,
        "order_id": order.id,
        "order_number": order.order_number,
        "order_line_id": line.id,
        "order_produced_qty": line.produced_qty,
        "approved_qty": line.approved_qty,
        "dispatched_qty": line.dispatched_qty,
        "pending_production_qty": max(
            Decimal(line.ordered_qty) - Decimal(line.produced_qty),
            Decimal("0"),
        ),
        "order_status": order.status,
        "inventory_posted": False,
    }


@router.get("/plans/{plan_id}/history")
def plan_history(plan_id: int, db: Session = Depends(get_db)):
    company = active_company(db)
    plan = plan_or_404(db, company.id, plan_id)
    events = db.scalars(
        select(PlanningEvent)
        .where(PlanningEvent.plan_id == plan.id)
        .order_by(PlanningEvent.occurred_at, PlanningEvent.id)
    ).all()

    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "before_data": item.before_data,
            "after_data": item.after_data,
            "reason": item.reason,
            "occurred_at": item.occurred_at,
        }
        for item in events
    ]
