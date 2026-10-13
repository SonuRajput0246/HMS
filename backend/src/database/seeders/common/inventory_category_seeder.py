from sqlalchemy import select
from src.database.session import db_session
from src.api.models.common.inventory_category_model import InventoryCategory
from datetime import datetime, timezone

categories = [
    {"name": "Food", "description": "Raw food materials used in kitchen"},
    {"name": "Beverage", "description": "Drinks and beverage items"},
    {"name": "Housekeeping", "description": "Housekeeping consumables and supplies"},
    {"name": "Maintenance", "description": "Maintenance and repair materials"},
    {"name": "Laundry", "description": "Laundry-related items and supplies"}
]

def seed_inventory_categories():
    try:
        for cat in categories:
            ## Modern 2.0 syntax: Check if category exists
            stmt = select(InventoryCategory).filter_by(name=cat["name"], is_deleted=False)
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                category = InventoryCategory(
                    name=cat["name"],
                    description=cat["description"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(category)

        db_session.commit()
        print("--- Inventory categories seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding inventory categories:", str(e))

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_inventory_categories()
