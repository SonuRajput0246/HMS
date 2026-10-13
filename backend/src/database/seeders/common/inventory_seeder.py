from sqlalchemy import select
from src.database.session import db_session
from src.api.models.common.inventory_model import Inventory
from src.api.models.common.inventory_category_model import InventoryCategory
from datetime import datetime, timezone


inventory_items = [
    ## Food
    {"name": "Rice", "unit_cost": "45.00", "category": "Food", "quantity": 100, "unit": "kg"},
    {"name": "Cooking Oil", "unit_cost": "180.00", "category": "Food", "quantity": 50, "unit": "ltr"},
    {"name": "Sugar", "unit_cost": "50.00", "category": "Food", "quantity": 40, "unit": "kg"},

    ## The rest of the kitchen. Kept so stock valuation has a realistic
    ## spread to report against rather than three staples.
    {"name": "Wheat Flour", "unit_cost": "40.00", "category": "Food", "quantity": 60, "unit": "kg"},
    {"name": "Paneer", "unit_cost": "320.00", "category": "Food", "quantity": 20, "unit": "kg"},
    {"name": "Chicken", "unit_cost": "280.00", "category": "Food", "quantity": 25, "unit": "kg"},
    {"name": "Tomato", "unit_cost": "30.00", "category": "Food", "quantity": 15, "unit": "kg"},
    {"name": "Onion", "unit_cost": "35.00", "category": "Food", "quantity": 15, "unit": "kg"},
    {"name": "Potato", "unit_cost": "25.00", "category": "Food", "quantity": 20, "unit": "kg"},
    {"name": "Coffee Powder", "unit_cost": "800.00", "category": "Food", "quantity": 5, "unit": "kg"},

    ## Beverage
    {"name": "Mineral Water Bottle", "unit_cost": "20.00", "category": "Beverage", "quantity": 200, "unit": "pcs"},
    {"name": "Soft Drinks", "unit_cost": "35.00", "category": "Beverage", "quantity": 120, "unit": "pcs"},
    {"name": "Milk", "unit_cost": "60.00", "category": "Beverage", "quantity": 40, "unit": "ltr"},
    {"name": "Tea Powder", "unit_cost": "400.00", "category": "Beverage", "quantity": 3, "unit": "kg"},

    ## Housekeeping
    {"name": "Soap", "unit_cost": "12.00", "category": "Housekeeping", "quantity": 300, "unit": "pcs"},
    {"name": "Shampoo Sachet", "unit_cost": "8.00", "category": "Housekeeping", "quantity": 250, "unit": "pcs"},
    {"name": "Towels", "unit_cost": "150.00", "category": "Housekeeping", "quantity": 150, "unit": "pcs"},

    ## Maintenance
    {"name": "Light Bulbs", "unit_cost": "45.00", "category": "Maintenance", "quantity": 60, "unit": "pcs"},
    {"name": "Cleaning Chemicals", "unit_cost": "180.00", "category": "Maintenance", "quantity": 25, "unit": "ltr"},

    ## Laundry
    {"name": "Detergent Powder", "unit_cost": "120.00", "category": "Laundry", "quantity": 80, "unit": "kg"},
    {"name": "Fabric Softener", "unit_cost": "220.00", "category": "Laundry", "quantity": 30, "unit": "ltr"}
]

def seed_inventories():
    try:
        ## 1. Fetch all active categories into a loopup directory { "Food": 1, "Beverage": 2 }
        cat_stmt = select(InventoryCategory).filter_by(is_deleted=False)
        category_records = db_session.execute(cat_stmt).scalars().all()

        category_map = {c.name: c.id for c in category_records}

        for item in inventory_items:
            category_id = category_map.get(item["category"])

            if not category_id:
                print(f"Skipping {item['name']}: Category {item['category']} not found.")
                continue

            ## 2. Check if the item already exists using SQLAlchemy 2.0 select
            exists_stmt = select(Inventory).filter_by(
                name=item["name"],
                category_id=category_id,
                is_deleted=False
            )
            exists = db_session.execute(exists_stmt).scalar_one_or_none()

            if exists:
                ## Keep the cost in step with the seeder. An operator's own
                ## purchase price is edited on the inventory screen, not here,
                ## so overwriting keeps a re-seed from leaving a stale figure.
                ## quantity is deliberately NOT touched: that is live stock,
                ## and a re-seed must not reset what the business has issued.
                exists.unit_cost = item.get("unit_cost")
                exists.updated_at = datetime.now(timezone.utc)
            else:
                ## BaseModel handles created_at and is_deleted automatically
                new_item = Inventory(
                    name=item["name"],
                    category_id=category_id,
                    quantity=item["quantity"],
                    unit=item["unit"],
                    ## Left NULL, unit_cost is read as 0 and stock valuation
                    ## silently reports the whole book as worthless.
                    unit_cost=item.get("unit_cost"),
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(new_item)

        db_session.commit()
        print("--- Inventory items seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        ## Raise rather than print-and-return: this swallowed a NameError once
        ## and the run reported success with no inventory written at all.
        print("!!! Inventory seeder FAILED: "
              + str(e).encode("ascii", "replace").decode("ascii")[:300])
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_inventories()
