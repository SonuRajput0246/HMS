from datetime import datetime, timezone
from sqlalchemy import select

from src.api.models.cms.recipe_category_model import RecipeCategory
from src.database.session import db_session


## Standard cafe menu sections. Seeder-only so a new install has a usable menu
## scaffold; a cafe is free to rename, reorder or delete any of them.
recipe_categories_data = [
    {"name": "starters", "display_name": "Starters", "display_order": 1, "description": "Small plates to begin"},
    {"name": "main_course", "display_name": "Main Course", "display_order": 2, "description": "Main dishes"},
    {"name": "breads", "display_name": "Breads & Rotis", "display_order": 3, "description": "Freshly baked breads"},
    {"name": "rice", "display_name": "Rice & Biryani", "display_order": 4, "description": "Rice preparations"},
    {"name": "desserts", "display_name": "Desserts", "display_order": 5, "description": "Sweet course"},
    {"name": "beverages", "display_name": "Beverages", "display_order": 6, "description": "Hot and cold drinks"},
]


def seed_recipe_categories():
    """Idempotent: matched on `name`, which is the stable key.

    Runs on both instances -- the categories table is harmless on HMS and the
    cost is 6 rows. Gating it on INSTANCE_TYPE would mean an operator who
    switches a CMS instance back to HMS and forward again loses nothing, but
    would also gain nothing.
    """
    try:
        for row in recipe_categories_data:
            stmt = select(RecipeCategory).filter_by(name=row["name"], is_deleted=False)
            exists = db_session.execute(stmt).scalar_one_or_none()

            if exists:
                ## Keep labels and ordering in sync with the seeder without
                ## disturbing anything an admin customised beyond those fields.
                exists.display_name = row["display_name"]
                exists.description = row["description"]
                exists.display_order = row["display_order"]
                exists.is_active = True
                exists.updated_at = datetime.now(timezone.utc)
                continue

            db_session.add(RecipeCategory(
                name=row["name"],
                display_name=row["display_name"],
                description=row["description"],
                display_order=row["display_order"],
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            ))

        db_session.commit()
        print("--- Recipe categories seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding recipe categories:", str(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_recipe_categories()