from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Branch, Company, Machine, MachineRPMReading, Shift, ProductionShiftEntry,
    Party, PlanningAllocation, ProductionPlan, SalesOrder,
    SalesOrderLine, Worker,
)
from app.schemas.production import (
    ProductionShiftEntryCreate,
    ProductionMaterialRecipeCreate,
    MachineStandardRPMUpdate,
    MachineRPMReadingCreate,
)
from app.models.core import Product
from app.models.textile import MachineType
from app.models.inventory import StockStage
from app.models.production import (
    ProductionMaterialRecipe,
    ProductionMaterialRecipeLine,
)



class MachineSetupCreate(BaseModel):
    machine_name: str = Field(min_length=1, max_length=100)
    standard_rpm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


router = APIRouter(prefix="/api/v1/production", tags=["Production Management"])


def active_company(db: Session) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.id)
    )
    if not company:
        raise HTTPException(409, "Factory company is not initialized.")
    return company


def date_filter(query, date_from: date | None, date_to: date | None):
    if date_from:
        query = query.where(ProductionShiftEntry.work_date >= date_from)
    if date_to:
        query = query.where(ProductionShiftEntry.work_date <= date_to)
    return query


def entry_dict(entry, machine, shift):
    target = Decimal(entry.target_output)
    actual = Decimal(entry.actual_output)
    achievement = (actual / target * 100) if target else Decimal("0")
    return {
        "id": entry.id,
        "work_date": entry.work_date,
        "machine_id": entry.machine_id,
        "machine_code": machine.code,
        "machine_name": machine.name,
        "shift_id": entry.shift_id,
        "shift_name": shift.name,
        "unit_code": entry.unit_code,
        "target_output": target,
        "actual_output": actual,
        "achievement_percent": achievement.quantize(Decimal("0.01")),
        "notes": entry.notes,
        "created_at": entry.created_at,
    }


@router.get("/lookups")
def production_lookups(db: Session = Depends(get_db)):
    company = active_company(db)

    machines = db.execute(
        select(Machine, Branch)
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

    return {
        "machines": [
            {
                "id": machine.id,
                "code": machine.code,
                "name": machine.name,
                "branch_id": machine.branch_id,
                "branch_name": branch.name,
            }
            for machine, branch in machines
        ],
        "shifts": [
            {
                "id": shift.id,
                "code": shift.code,
                "name": shift.name,
                "start_time": shift.start_time,
                "end_time": shift.end_time,
            }
            for shift in shifts
        ],
    }


@router.get("/entries")
def production_entries(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    query = (
        select(ProductionShiftEntry, Machine, Shift)
        .join(Machine, Machine.id == ProductionShiftEntry.machine_id)
        .join(Shift, Shift.id == ProductionShiftEntry.shift_id)
        .where(ProductionShiftEntry.company_id == company.id)
    )
    query = date_filter(query, date_from, date_to)

    rows = db.execute(
        query.order_by(
            ProductionShiftEntry.work_date.desc(),
            Machine.name,
            Shift.sequence_no,
            ProductionShiftEntry.id.desc(),
        )
    ).all()

    return [
        entry_dict(entry, machine, shift)
        for entry, machine, shift in rows
    ]


@router.get("/summary")
def production_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    query = (
        select(ProductionShiftEntry, Machine)
        .join(Machine, Machine.id == ProductionShiftEntry.machine_id)
        .where(ProductionShiftEntry.company_id == company.id)
    )
    query = date_filter(query, date_from, date_to)
    rows = db.execute(query).all()

    totals = {
        "metres": {"target": Decimal("0"), "actual": Decimal("0")},
        "pieces": {"target": Decimal("0"), "actual": Decimal("0")},
    }
    machine_totals = {}

    for entry, machine in rows:
        unit = entry.unit_code
        target = Decimal(entry.target_output)
        actual = Decimal(entry.actual_output)

        totals[unit]["target"] += target
        totals[unit]["actual"] += actual

        key = (machine.id, unit)
        if key not in machine_totals:
            machine_totals[key] = {
                "machine_id": machine.id,
                "machine_code": machine.code,
                "machine_name": machine.name,
                "unit_code": unit,
                "target_output": Decimal("0"),
                "actual_output": Decimal("0"),
            }
        machine_totals[key]["target_output"] += target
        machine_totals[key]["actual_output"] += actual

    by_machine = []
    for item in machine_totals.values():
        target = item["target_output"]
        actual = item["actual_output"]
        item["achievement_percent"] = (
            (actual / target * 100).quantize(Decimal("0.01"))
            if target else Decimal("0")
        )
        by_machine.append(item)

    by_machine.sort(
        key=lambda item: (
            item["unit_code"], -float(item["achievement_percent"]),
            item["machine_name"].lower()
        )
    )

    for unit in totals:
        target = totals[unit]["target"]
        actual = totals[unit]["actual"]
        totals[unit]["achievement_percent"] = (
            (actual / target * 100).quantize(Decimal("0.01"))
            if target else Decimal("0")
        )

    return {
        "totals": totals,
        "by_machine": by_machine,
        "entry_count": len(rows),
    }


@router.post("/entries", status_code=201)
def create_production_entry(
    payload: ProductionShiftEntryCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    machine = db.scalar(
        select(Machine).where(
            Machine.id == payload.machine_id,
            Machine.company_id == company.id,
            Machine.is_active.is_(True),
        )
    )
    if not machine:
        raise HTTPException(404, "Active machine not found for this company.")

    branch = db.scalar(
        select(Branch).where(
            Branch.id == machine.branch_id,
            Branch.company_id == company.id,
            Branch.is_active.is_(True),
        )
    )
    if not branch:
        raise HTTPException(409, "The selected machine's branch is inactive.")

    shift = db.scalar(
        select(Shift).where(
            Shift.id == payload.shift_id,
            Shift.company_id == company.id,
            Shift.is_active.is_(True),
        )
    )
    if not shift:
        raise HTTPException(404, "Active shift not found for this company.")

    entry = ProductionShiftEntry(
        company_id=company.id,
        branch_id=machine.branch_id,
        machine_id=machine.id,
        shift_id=shift.id,
        work_date=payload.work_date,
        unit_code=payload.unit_code,
        target_output=payload.target_output,
        actual_output=payload.actual_output,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry_dict(entry, machine, shift)

@router.get("/machine-overview")
def production_machine_overview(db: Session = Depends(get_db)):
    """
    Owner-facing machine overview assembled from existing machine,
    planning, order and worker records. This endpoint is read-only.
    """
    company = active_company(db)
    now = datetime.now(timezone.utc)

    machines = db.scalars(
        select(Machine)
        .where(
            Machine.company_id == company.id,
            Machine.is_active.is_(True),
        )
        .order_by(Machine.name, Machine.id)
    ).all()

    plans = db.scalars(
        select(ProductionPlan).where(
            ProductionPlan.company_id == company.id,
            ProductionPlan.status.in_(("scheduled", "in_progress")),
        )
    ).all()

    plan_ids = [plan.id for plan in plans]
    allocations = []
    if plan_ids:
        allocations = db.scalars(
            select(PlanningAllocation)
            .where(PlanningAllocation.plan_id.in_(plan_ids))
            .order_by(PlanningAllocation.starts_at, PlanningAllocation.id)
        ).all()

    plan_by_id = {plan.id: plan for plan in plans}

    def normalized(value):
        return " ".join((value or "").casefold().split())

    result = []

    for machine in machines:
        machine_allocations = []

        for allocation in allocations:
            linked_by_id = allocation.machine_id == machine.id
            linked_by_name = (
                allocation.manual_entry
                and normalized(allocation.machine_name_snapshot)
                in {normalized(machine.name), normalized(machine.code)}
            )
            if linked_by_id or linked_by_name:
                plan = plan_by_id.get(allocation.plan_id)
                if plan:
                    machine_allocations.append((allocation, plan))

        current = [
            pair for pair in machine_allocations
            if pair[0].starts_at <= now < pair[0].ends_at
        ]
        upcoming = [
            pair for pair in machine_allocations
            if pair[0].starts_at > now
        ]

        current.sort(key=lambda pair: (
            pair[0].starts_at,
            pair[0].id,
        ))
        upcoming.sort(key=lambda pair: (pair[0].starts_at, pair[0].id))

        # A plan's in_progress status does not mean its future shift is
        # already running. Machine status follows the allocation time.
        selected = current[0] if current else (
            upcoming[0] if upcoming else None
        )
        next_pair = (
            upcoming[0] if current and upcoming
            else upcoming[1] if selected and len(upcoming) > 1
            else None
        )

        def allocation_details(pair):
            if not pair:
                return None

            allocation, plan = pair
            order = db.get(SalesOrder, plan.sales_order_id)
            line = db.get(SalesOrderLine, plan.sales_order_line_id)
            customer = db.get(Party, order.customer_id) if order else None
            worker = (
                db.get(Worker, allocation.worker_id)
                if allocation.worker_id else None
            )
            shift = (
                db.get(Shift, allocation.shift_id)
                if allocation.shift_id else None
            )

            ordered_qty = Decimal(line.ordered_qty) if line else Decimal("0")
            order_produced = (
                Decimal(line.produced_qty) if line else Decimal("0")
            )
            planned_qty = Decimal(plan.planned_qty)
            actual_qty = Decimal(plan.actual_qty)

            return {
                "plan_id": plan.id,
                "plan_number": plan.plan_number,
                "plan_status": plan.status,
                "order_id": order.id if order else None,
                "order_number": order.order_number if order else None,
                "order_status": order.status if order else None,
                "customer_name": customer.name if customer else None,
                "delivery_date": order.delivery_date if order else None,
                "order_line_id": line.id if line else None,
                "product_id": line.product_id if line else None,
                "product_description": line.description if line else None,
                "design_code": line.design_code if line else None,
                "material": line.material if line else None,
                "colour": line.colour if line else None,
                "shade_code": line.shade_code if line else None,
                "width_mm": line.width_mm if line else None,
                "gsm": line.gsm if line else None,
                "ordered_qty": ordered_qty,
                "order_produced_qty": order_produced,
                "order_pending_qty": max(
                    Decimal("0"), ordered_qty - order_produced
                ),
                "planned_qty": planned_qty,
                "plan_actual_qty": actual_qty,
                "plan_pending_qty": max(
                    Decimal("0"), planned_qty - actual_qty
                ),
                "uom_code": plan.uom_code,
                "worker_id": allocation.worker_id,
                "worker_name": (
                    worker.full_name if worker
                    else allocation.worker_name_snapshot
                ),
                "shift_id": allocation.shift_id,
                "shift_name": shift.name if shift else None,
                "starts_at": allocation.starts_at,
                "ends_at": allocation.ends_at,
                "work_date": allocation.work_date,
                "manual_allocation": allocation.manual_entry,
            }

        selected_details = allocation_details(selected)
        next_details = allocation_details(next_pair)

        if current:
            status = "running"
        elif selected:
            status = "scheduled"
        else:
            status = "idle"

        result.append({
            "machine_id": machine.id,
            "machine_code": machine.code,
            "machine_name": machine.name,
            "branch_id": machine.branch_id,
            "machine_type_id": machine.machine_type_id,
            "status": status,
            "current_job": selected_details,
            "next_job": next_details,
        })

    return {
        "generated_at": now,
        "machine_count": len(result),
        "running_count": sum(1 for item in result if item["status"] == "running"),
        "scheduled_count": sum(1 for item in result if item["status"] == "scheduled"),
        "idle_count": sum(1 for item in result if item["status"] == "idle"),
        "machines": result,
    }



# ---------------------------------------------------------------------------
# Production material recipe master
# These endpoints only maintain recipe specifications. They never post stock.
# ---------------------------------------------------------------------------

def recipe_line_dict(db: Session, line: ProductionMaterialRecipeLine):
    material = db.get(Product, line.material_product_id)
    stage = db.get(StockStage, line.stock_stage_id)
    return {
        "id": line.id,
        "line_number": line.line_number,
        "material_product_id": line.material_product_id,
        "material_sku": material.sku if material else None,
        "material_name": material.name if material else None,
        "stock_stage_id": line.stock_stage_id,
        "stock_stage_name": stage.name if stage else None,
        "quantity_per_basis": line.quantity_per_basis,
        "quantity_uom_code": line.quantity_uom_code,
        "wastage_percent": line.wastage_percent,
        "notes": line.notes,
    }


def recipe_dict(db: Session, recipe: ProductionMaterialRecipe):
    product = db.get(Product, recipe.product_id)
    lines = db.scalars(
        select(ProductionMaterialRecipeLine)
        .where(ProductionMaterialRecipeLine.recipe_id == recipe.id)
        .order_by(ProductionMaterialRecipeLine.line_number)
    ).all()

    return {
        "id": recipe.id,
        "company_id": recipe.company_id,
        "product_id": recipe.product_id,
        "product_sku": product.sku if product else None,
        "product_name": product.name if product else None,
        "recipe_code": recipe.recipe_code,
        "version": recipe.version,
        "design_code": recipe.design_code,
        "basis_quantity": recipe.basis_quantity,
        "basis_uom_code": recipe.basis_uom_code,
        "is_active": recipe.is_active,
        "notes": recipe.notes,
        "created_at": recipe.created_at,
        "lines": [recipe_line_dict(db, line) for line in lines],
    }


def validate_recipe_payload(db: Session, company_id: int, payload):
    product = db.scalar(
        select(Product).where(
            Product.id == payload.product_id,
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_inventory_tracked.is_(True),
            Product.product_type == "finished_good",
        )
    )
    if not product:
        raise HTTPException(
            422,
            "Select an active, inventory-tracked finished-good product."
        )

    line_numbers = [line.line_number for line in payload.lines]
    if len(line_numbers) != len(set(line_numbers)):
        raise HTTPException(422, "Recipe line numbers must be unique.")

    material_ids = {line.material_product_id for line in payload.lines}
    materials = db.scalars(
        select(Product).where(
            Product.id.in_(material_ids),
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_inventory_tracked.is_(True),
            Product.product_type.in_(("raw_material", "semi_finished")),
        )
    ).all()
    valid_material_ids = {item.id for item in materials}

    for line in payload.lines:
        if line.material_product_id not in valid_material_ids:
            raise HTTPException(
                422,
                f"Material product ID {line.material_product_id} is not an active, inventory-tracked raw material or semi-finished product."
            )

    stage_ids = {line.stock_stage_id for line in payload.lines}
    stages = db.scalars(
        select(StockStage).where(
            StockStage.id.in_(stage_ids),
            StockStage.company_id == company_id,
            StockStage.is_active.is_(True),
            StockStage.stage_type.in_(
                ("raw_material", "grey_fabric", "work_in_progress")
            ),
        )
    ).all()
    valid_stage_ids = {item.id for item in stages}

    for line in payload.lines:
        if line.stock_stage_id not in valid_stage_ids:
            raise HTTPException(
                422,
                f"Stock stage ID {line.stock_stage_id} is not an active material/WIP stage."
            )

    return product


def add_recipe_lines(db: Session, recipe_id: int, lines):
    for item in lines:
        db.add(
            ProductionMaterialRecipeLine(
                recipe_id=recipe_id,
                line_number=item.line_number,
                material_product_id=item.material_product_id,
                stock_stage_id=item.stock_stage_id,
                quantity_per_basis=item.quantity_per_basis,
                quantity_uom_code=item.quantity_uom_code,
                wastage_percent=item.wastage_percent,
                notes=item.notes.strip() if item.notes else None,
            )
        )


@router.get("/recipes/lookups")
def production_recipe_lookups(db: Session = Depends(get_db)):
    company = active_company(db)

    products = db.scalars(
        select(Product).where(
            Product.company_id == company.id,
            Product.is_active.is_(True),
            Product.is_inventory_tracked.is_(True),
            Product.product_type.in_((
                "finished_good", "raw_material", "semi_finished"
            )),
        ).order_by(Product.name, Product.id)
    ).all()

    stages = db.scalars(
        select(StockStage).where(
            StockStage.company_id == company.id,
            StockStage.is_active.is_(True),
            StockStage.stage_type.in_(
                ("raw_material", "grey_fabric", "work_in_progress")
            ),
        ).order_by(StockStage.name, StockStage.id)
    ).all()

    return {
        "finished_products": [
            {"id": item.id, "sku": item.sku, "name": item.name}
            for item in products if item.product_type == "finished_good"
        ],
        "materials": [
            {
                "id": item.id,
                "sku": item.sku,
                "name": item.name,
                "product_type": item.product_type,
            }
            for item in products
            if item.product_type in ("raw_material", "semi_finished")
        ],
        "stock_stages": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "stage_type": item.stage_type,
            }
            for item in stages
        ],
    }


@router.get("/recipes")
def list_production_recipes(
    product_id: int | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    query = select(ProductionMaterialRecipe).where(
        ProductionMaterialRecipe.company_id == company.id
    )
    if product_id:
        query = query.where(ProductionMaterialRecipe.product_id == product_id)
    if active_only:
        query = query.where(ProductionMaterialRecipe.is_active.is_(True))

    recipes = db.scalars(
        query.order_by(
            ProductionMaterialRecipe.product_id,
            ProductionMaterialRecipe.recipe_code,
            ProductionMaterialRecipe.version.desc(),
        )
    ).all()

    return [recipe_dict(db, recipe) for recipe in recipes]


@router.get("/recipes/{recipe_id}")
def get_production_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    recipe = db.scalar(
        select(ProductionMaterialRecipe).where(
            ProductionMaterialRecipe.id == recipe_id,
            ProductionMaterialRecipe.company_id == company.id,
        )
    )
    if not recipe:
        raise HTTPException(404, "Production recipe not found.")
    return recipe_dict(db, recipe)


@router.post("/recipes", status_code=201)
def create_production_recipe(
    payload: ProductionMaterialRecipeCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    validate_recipe_payload(db, company.id, payload)

    code = payload.recipe_code.strip()
    if not code:
        raise HTTPException(422, "Recipe code cannot be blank.")

    duplicate = db.scalar(
        select(ProductionMaterialRecipe.id).where(
            ProductionMaterialRecipe.company_id == company.id,
            ProductionMaterialRecipe.product_id == payload.product_id,
            ProductionMaterialRecipe.recipe_code == code,
            ProductionMaterialRecipe.version == 1,
        )
    )
    if duplicate:
        raise HTTPException(
            409,
            "This recipe code already exists for the selected product. Create a new version instead."
        )

    recipe = ProductionMaterialRecipe(
        company_id=company.id,
        product_id=payload.product_id,
        recipe_code=code,
        version=1,
        design_code=payload.design_code.strip() if payload.design_code else None,
        basis_quantity=payload.basis_quantity,
        basis_uom_code=payload.basis_uom_code,
        is_active=True,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(recipe)
    db.flush()
    add_recipe_lines(db, recipe.id, payload.lines)
    db.commit()
    db.refresh(recipe)
    return recipe_dict(db, recipe)


@router.post("/recipes/{recipe_id}/new-version", status_code=201)
def create_production_recipe_version(
    recipe_id: int,
    payload: ProductionMaterialRecipeCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    original = db.scalar(
        select(ProductionMaterialRecipe).where(
            ProductionMaterialRecipe.id == recipe_id,
            ProductionMaterialRecipe.company_id == company.id,
        )
    )
    if not original:
        raise HTTPException(404, "Original production recipe not found.")

    if (
        payload.product_id != original.product_id
        or payload.recipe_code.strip() != original.recipe_code
    ):
        raise HTTPException(
            422,
            "A new version must retain the original product and recipe code."
        )

    validate_recipe_payload(db, company.id, payload)

    latest_version = db.scalar(
        select(func.max(ProductionMaterialRecipe.version)).where(
            ProductionMaterialRecipe.company_id == company.id,
            ProductionMaterialRecipe.product_id == original.product_id,
            ProductionMaterialRecipe.recipe_code == original.recipe_code,
        )
    ) or original.version

    versions = db.scalars(
        select(ProductionMaterialRecipe).where(
            ProductionMaterialRecipe.company_id == company.id,
            ProductionMaterialRecipe.product_id == original.product_id,
            ProductionMaterialRecipe.recipe_code == original.recipe_code,
        )
    ).all()
    for version in versions:
        version.is_active = False

    recipe = ProductionMaterialRecipe(
        company_id=company.id,
        product_id=original.product_id,
        recipe_code=original.recipe_code,
        version=latest_version + 1,
        design_code=payload.design_code.strip() if payload.design_code else None,
        basis_quantity=payload.basis_quantity,
        basis_uom_code=payload.basis_uom_code,
        is_active=True,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(recipe)
    db.flush()
    add_recipe_lines(db, recipe.id, payload.lines)
    db.commit()
    db.refresh(recipe)
    return recipe_dict(db, recipe)


def rpm_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def rpm_reading_dict(reading, machine):
    standard = Decimal(reading.standard_rpm)
    actual = Decimal(reading.actual_rpm)
    performance = (actual / standard * 100) if standard else Decimal("0")
    return {
        "id": reading.id,
        "machine_id": machine.id,
        "machine_code": machine.code,
        "recorded_at": reading.recorded_at,
        "actual_rpm": actual,
        "standard_rpm": standard,
        "performance_percent": performance.quantize(Decimal("0.01")),
    }


@router.get("/rpm/lookups")
def machine_rpm_lookups(db: Session = Depends(get_db)):
    company = active_company(db)
    rows = db.execute(
        select(Machine, Branch)
        .join(Branch, Branch.id == Machine.branch_id)
        .where(
            Machine.company_id == company.id,
            Machine.is_active.is_(True),
            Branch.is_active.is_(True),
        )
        .order_by(Machine.id)
    ).all()

    return {
        "machines": [
            {
                "id": machine.id,
                "code": machine.code,
                "name": machine.name,
                "standard_rpm": machine.rpm,
                "branch_id": machine.branch_id,
                "branch_name": branch.name,
            }
            for machine, branch in rows
        ]
    }




@router.post("/rpm/machines", status_code=201)
def create_rpm_machine(
    payload: MachineSetupCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)

    branch = db.scalar(
        select(Branch)
        .where(
            Branch.company_id == company.id,
            Branch.is_active.is_(True),
        )
        .order_by(Branch.id)
    )
    if not branch:
        raise HTTPException(409, "Create an active factory branch first.")

    machine_type = db.scalar(
        select(MachineType).where(
            MachineType.company_id == company.id,
            MachineType.code == "FACTORY-MACHINE",
        )
    )
    if not machine_type:
        machine_type = MachineType(
            company_id=company.id,
            code="FACTORY-MACHINE",
            name="Factory Machine",
            is_active=True,
        )
        db.add(machine_type)
        db.flush()

    highest_id = db.scalar(
        select(func.max(Machine.id)).where(Machine.company_id == company.id)
    ) or 0
    next_number = highest_id + 1
    machine_code = f"KDK-MACHINE-{next_number:03d}"

    while db.scalar(
        select(Machine.id).where(
            Machine.company_id == company.id,
            Machine.code == machine_code,
        )
    ) is not None:
        next_number += 1
        machine_code = f"KDK-MACHINE-{next_number:03d}"

    machine = Machine(
        company_id=company.id,
        branch_id=branch.id,
        machine_type_id=machine_type.id,
        code=machine_code,
        name=payload.machine_name.strip(),
        rpm=payload.standard_rpm,
        is_active=True,
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)

    return {
        "machine_id": machine.id,
        "machine_code": machine.code,
        "machine_name": machine.name,
        "standard_rpm": machine.rpm,
        "message": f"{machine.name} registered successfully.",
    }


@router.put("/rpm/machines/{machine_id}/standard")
def update_machine_standard_rpm(
    machine_id: int,
    payload: MachineStandardRPMUpdate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    machine = db.scalar(
        select(Machine).where(
            Machine.id == machine_id,
            Machine.company_id == company.id,
            Machine.is_active.is_(True),
        )
    )
    if not machine:
        raise HTTPException(404, "Active machine not found.")

    machine.rpm = payload.standard_rpm
    db.commit()
    db.refresh(machine)
    return {
        "machine_id": machine.id,
        "standard_rpm": machine.rpm,
        "message": "Standard RPM saved.",
    }


@router.post("/rpm/readings", status_code=201)
def create_machine_rpm_reading(
    payload: MachineRPMReadingCreate,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    machine = db.scalar(
        select(Machine).where(
            Machine.id == payload.machine_id,
            Machine.company_id == company.id,
            Machine.is_active.is_(True),
        )
    )
    if not machine:
        raise HTTPException(404, "Active machine not found.")
    if machine.rpm is None or Decimal(machine.rpm) <= 0:
        raise HTTPException(
            409,
            "Set this machine's Standard RPM before recording a reading.",
        )

    reading = MachineRPMReading(
        company_id=company.id,
        branch_id=machine.branch_id,
        machine_id=machine.id,
        recorded_at=rpm_as_utc(payload.recorded_at),
        actual_rpm=payload.actual_rpm,
        standard_rpm=machine.rpm,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return rpm_reading_dict(reading, machine)


@router.get("/rpm/readings")
def list_machine_rpm_readings(
    machine_id: int | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    db: Session = Depends(get_db),
):
    company = active_company(db)
    query = (
        select(MachineRPMReading, Machine)
        .join(Machine, Machine.id == MachineRPMReading.machine_id)
        .where(MachineRPMReading.company_id == company.id)
    )

    if machine_id:
        query = query.where(MachineRPMReading.machine_id == machine_id)

    if from_at:
        query = query.where(
            MachineRPMReading.recorded_at >= rpm_as_utc(from_at)
        )
    elif not to_at:
        query = query.where(
            MachineRPMReading.recorded_at >=
            datetime.now(timezone.utc) - timedelta(hours=6)
        )

    if to_at:
        query = query.where(
            MachineRPMReading.recorded_at <= rpm_as_utc(to_at)
        )

    rows = db.execute(
        query.order_by(MachineRPMReading.recorded_at.desc())
        .limit(500)
    ).all()

    return [rpm_reading_dict(reading, machine) for reading, machine in rows]
