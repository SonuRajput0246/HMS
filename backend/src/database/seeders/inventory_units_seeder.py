from sqlalchemy import select
from src.database.session import db_session
from src.api.models.inventory_units_model import InventoryUnits
from datetime import datetime, timezone

inventory_units = [
    {"code": "kg", "label": "Kilogram (kg)"},
    {"code": "gm", "label": "Gram (gm)"},
    {"code": "ltr", "label": "Liter (ltr)"},
    {"code": "ml", "label": "Milliliter (ml)"},
    {"code": "pcs", "label": "Pieces (pcs)"}
]

def seed_inventory_units():
    try:
        for unit in inventory_units:
            ## Modern 2.0 syntax: Check if category exists
            stmt = select(InventoryUnits).filter_by(code=unit["code"])
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                new_item = InventoryUnits(
                    code=unit["code"],
                    label=unit["label"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(new_item)

        db_session.commit()
        print("--- Inventory units seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print(f"!!! Error seeding inventory units: {str(e)}")

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_inventory_units()
