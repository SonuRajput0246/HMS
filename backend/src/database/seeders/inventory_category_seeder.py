from sqlalchemy import select
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from src.api.models.inventory_category_model import InventoryCategory
from datetime import datetime, timezone

categories = [
    {"name": "Food", "description": "Raw food materials used in kitchen"},
    {"name": "Beverage", "description": "Drinks and beverage items"},
    {"name": "Housekeeping", "description": "Housekeeping consumables and supplies"},
    {"name": "Maintenance", "description": "Maintenance and repair materials"},
    {"name": "Laundry", "description": "Laundry-related items and supplies"}
]

def seed_inventory_categories(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for cat in categories:
            ## Modern 2.0 syntax: Check if category exists.
            ## Scoped to the hotel: "Food" is a category every hotel has, and
            ## without the tenant filter the second hotel would be skipped as a
            ## duplicate of the first.
            stmt = select(InventoryCategory).filter_by(
                tenant_id=tenant_id,
                name=cat["name"],
                is_deleted=False
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                category = InventoryCategory(
                    tenant_id=tenant_id,
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
        print("!!! Error seeding inventory categories:", safe_error(e))
        raise

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_inventory_categories()
