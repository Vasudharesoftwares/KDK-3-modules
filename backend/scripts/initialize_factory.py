from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Company, Branch, Warehouse, StockStage, UnitOfMeasure
)

db = SessionLocal()

try:
    company = db.scalar(select(Company).where(Company.code == "KDK"))
    if company is None:
        company = Company(
            code="KDK",
            legal_name="KAY DEE KAY",
            display_name="KAY DEE KAY",
            state="Punjab",
            country="India",
            is_active=True,
        )
        db.add(company)
        db.flush()

    branch = db.scalar(select(Branch).where(
        Branch.company_id == company.id,
        Branch.code == "MAIN"
    ))
    if branch is None:
        branch = Branch(
            company_id=company.id,
            code="MAIN",
            name="Main Factory",
            city="Amritsar",
            state="Punjab",
            is_head_office=True,
            is_active=True,
        )
        db.add(branch)
        db.flush()

    warehouse = db.scalar(select(Warehouse).where(
        Warehouse.branch_id == branch.id,
        Warehouse.code == "MAIN"
    ))
    if warehouse is None:
        db.add(Warehouse(
            branch_id=branch.id,
            code="MAIN",
            name="Main Warehouse",
            warehouse_type="general",
            is_active=True,
        ))

    stages = [
        ("RAW", "Raw Material", "raw_material", False),
        ("GREY", "Grey Fabric", "grey_fabric", True),
        ("WIP", "Work in Progress", "work_in_progress", True),
        ("FG", "Finished Goods", "finished_good", True),
        ("SCRAP", "Scrap", "scrap", False),
    ]
    for code, name, stage_type, tracks_rolls in stages:
        existing = db.scalar(select(StockStage).where(
            StockStage.company_id == company.id,
            StockStage.code == code
        ))
        if existing is None:
            db.add(StockStage(
                company_id=company.id,
                code=code,
                name=name,
                stage_type=stage_type,
                tracks_rolls=tracks_rolls,
                is_active=True,
            ))

    units = [
        ("M", "Metre", "m", 3),
        ("PCS", "Pieces", "pcs", 0),
        ("ROLL", "Roll", "roll", 0),
        ("KG", "Kilogram", "kg", 3),
    ]
    for code, name, symbol, decimals in units:
        existing = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == code))
        if existing is None:
            db.add(UnitOfMeasure(
                code=code,
                name=name,
                symbol=symbol,
                decimal_places=decimals,
                is_active=True,
            ))

    db.commit()
    print("Factory initialization successful.")
    print(f"Company ID: {company.id}")
    print(f"Branch ID: {branch.id}")
    print("Main warehouse, inventory stages and units are ready.")
    print("No customers, products, machines, workers or stock were created.")

except Exception:
    db.rollback()
    raise
finally:
    db.close()
