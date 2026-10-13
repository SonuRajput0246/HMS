"""Seeds CMS recipes with ingredient lines resolved against inventory.

The cost of a recipe is derived from its ingredient lines, so a recipe seeded
without ingredients would price at zero and make margin meaningless. Every
line here therefore points at a real inventory row, matched by name.

Neither the recipe nor its category is referenced by name anywhere else, so
categories resolve by name too. Nothing hardcodes an id: ids differ between a
fresh database and one that has been seeded before.

No order history is created, so no recipe carries sales -- these are menu
items only.

Idempotent, matched on `name`.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from src.api.models.common.inventory_model import Inventory
from src.api.models.cms.recipe_category_model import RecipeCategory
from src.api.models.cms.recipe_ingredient_model import RecipeIngredient
from src.api.models.cms.recipe_model import Recipe
from src.api.services.common.document_sequence_service import DocumentSequenceService
from src.database.session import db_session


## Station values must exist in enum_definitions.recipe_station. See
## enum_seeder.py -- renaming a key there orphans every historical order line,
## because recipes.station and cms_order_items.station are plain VARCHARs.
recipes_data = [
    {
        "name": "Paneer Tikka",
        "display_name": "Paneer Tikka",
        "category": "starters",
        "selling_price": "240.00",
        "station": "tandoor",
        "prep_time_minutes": 20,
        "cook_time_minutes": 15,
        "is_vegetarian": True,
        "is_vegan": False,
        "is_spicy": True,
        "default_spice_level": "medium",
        "is_recommended": True,
        "display_order": 1,
        "ingredients": [
            {"inventory": "Paneer", "quantity": "0.25", "unit": "kg"},
            {"inventory": "Onion", "quantity": "0.15", "unit": "kg"},
            {"inventory": "Tomato", "quantity": "0.10", "unit": "kg"},
            {"inventory": "Cooking Oil", "quantity": "0.05", "unit": "ltr"},
        ],
    },
    {
        "name": "Chicken Biryani",
        "display_name": "Chicken Biryani",
        "category": "rice",
        "selling_price": "320.00",
        "station": "grill",
        "prep_time_minutes": 25,
        "cook_time_minutes": 40,
        "is_vegetarian": False,
        "is_vegan": False,
        "is_spicy": True,
        "default_spice_level": "hot",
        "is_recommended": True,
        "display_order": 2,
        "ingredients": [
            {"inventory": "Rice", "quantity": "0.30", "unit": "kg"},
            {"inventory": "Chicken", "quantity": "0.25", "unit": "kg"},
            {"inventory": "Onion", "quantity": "0.10", "unit": "kg"},
            {"inventory": "Cooking Oil", "quantity": "0.04", "unit": "ltr"},
        ],
    },
    {
        "name": "Garlic Naan",
        "display_name": "Garlic Naan",
        "category": "breads",
        "selling_price": "90.00",
        "station": "tandoor",
        "prep_time_minutes": 15,
        "cook_time_minutes": 10,
        "is_vegetarian": True,
        "is_vegan": False,
        "is_spicy": False,
        "display_order": 3,
        "ingredients": [
            {"inventory": "Wheat Flour", "quantity": "0.20", "unit": "kg"},
            {"inventory": "Cooking Oil", "quantity": "0.02", "unit": "ltr"},
        ],
    },
    {
        "name": "Masala Dosa",
        "display_name": "Masala Dosa",
        "category": "main_course",
        "selling_price": "150.00",
        "station": "fry",
        "prep_time_minutes": 30,
        "cook_time_minutes": 10,
        "is_vegetarian": True,
        "is_vegan": False,
        "is_spicy": True,
        "default_spice_level": "mild",
        "display_order": 4,
        "ingredients": [
            {"inventory": "Rice", "quantity": "0.12", "unit": "kg"},
            {"inventory": "Potato", "quantity": "0.15", "unit": "kg"},
            {"inventory": "Cooking Oil", "quantity": "0.03", "unit": "ltr"},
        ],
    },
    {
        "name": "Masala Chai",
        "display_name": "Masala Chai",
        "category": "beverages",
        "selling_price": "50.00",
        "station": "bar",
        "prep_time_minutes": 5,
        "cook_time_minutes": 5,
        "is_vegetarian": True,
        "is_vegan": False,
        "is_spicy": False,
        "is_recommended": True,
        "display_order": 5,
        "ingredients": [
            {"inventory": "Milk", "quantity": "0.15", "unit": "ltr"},
            {"inventory": "Tea Powder", "quantity": "0.005", "unit": "kg"},
            {"inventory": "Sugar", "quantity": "0.01", "unit": "kg"},
        ],
    },
    {
        "name": "Cold Coffee",
        "display_name": "Cold Coffee",
        "category": "beverages",
        "selling_price": "140.00",
        "station": "bar",
        "prep_time_minutes": 5,
        "cook_time_minutes": 0,
        "is_vegetarian": True,
        "is_vegan": False,
        "default_spice_level": "none",
        "display_order": 6,
        "ingredients": [
            {"inventory": "Milk", "quantity": "0.20", "unit": "ltr"},
            {"inventory": "Coffee Powder", "quantity": "0.01", "unit": "kg"},
            {"inventory": "Sugar", "quantity": "0.015", "unit": "kg"},
        ],
    },
]


def _resolve_inventory():
    return {
        item.name: item
        for item in db_session.execute(
            select(Inventory).filter(Inventory.is_deleted == False)
        ).scalars().all()
    }


def _resolve_categories():
    return {
        cat.name: cat
        for cat in db_session.execute(
            select(RecipeCategory).filter(RecipeCategory.is_deleted == False)
        ).scalars().all()
    }


def _safe(message: str) -> str:
    return message.encode("ascii", "replace").decode("ascii")


def seed_recipes():
    inventory_by_name = _resolve_inventory()
    categories_by_name = _resolve_categories()
    ## recipe_code is NOT NULL and unique with no default. Same generator the
    ## API uses -- a hand-written code would either fail the insert or collide.
    sequence = DocumentSequenceService(db_session)

    missing_inv = sorted({
        line["inventory"]
        for row in recipes_data
        for line in row["ingredients"]
        if line["inventory"] not in inventory_by_name
    })
    if missing_inv:
        raise LookupError(
            f"recipe_seeder: inventory items not found: {missing_inv}. "
            f"Run inventory_seeder first."
        )

    missing_cat = sorted({
        row["category"] for row in recipes_data
        if row["category"] not in categories_by_name
    })
    if missing_cat:
        raise LookupError(
            f"recipe_seeder: recipe categories not found: {missing_cat}. "
            f"Run recipe_category_seeder first."
        )

    created = 0
    for row in recipes_data:
        recipe = db_session.execute(
            select(Recipe).filter_by(name=row["name"])
        ).scalars().first()

        if recipe:
            recipe.display_name = row["display_name"]
            recipe.category_id = categories_by_name[row["category"]].id
            recipe.selling_price = Decimal(row["selling_price"])
            recipe.station = row["station"]
            recipe.prep_time_minutes = row["prep_time_minutes"]
            recipe.cook_time_minutes = row["cook_time_minutes"]
            recipe.is_vegetarian = bool(row.get("is_vegetarian"))
            recipe.is_vegan = bool(row.get("is_vegan"))
            recipe.is_spicy = bool(row.get("is_spicy"))
            recipe.default_spice_level = row.get("default_spice_level", "none")
            recipe.is_recommended = bool(row.get("is_recommended"))
            recipe.display_order = row["display_order"]
            recipe.is_available = True
            recipe.updated_at = datetime.now(timezone.utc)
        else:
            recipe = Recipe(
                recipe_code=sequence.generate("recipe"),
                name=row["name"],
                display_name=row["display_name"],
                category_id=categories_by_name[row["category"]].id,
                selling_price=Decimal(row["selling_price"]),
                station=row["station"],
                prep_time_minutes=row["prep_time_minutes"],
                cook_time_minutes=row["cook_time_minutes"],
                ## .get with a default rather than row[...]: these columns are
                ## NOT NULL with no database default, so a missing key becomes a
                ## KeyError at insert. Requiring every row to spell out six
                ## booleans just meant one omission failed the whole seed.
                is_vegetarian=bool(row.get("is_vegetarian")),
                is_vegan=bool(row.get("is_vegan")),
                is_spicy=bool(row.get("is_spicy")),
                default_spice_level=row.get("default_spice_level", "none"),
                is_recommended=bool(row.get("is_recommended")),
                is_available=True,
                display_order=row["display_order"],
                is_active=True,
                is_deleted=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(recipe)
            created += 1

        db_session.flush()
        _seed_ingredients(recipe, row["ingredients"], inventory_by_name)

        ## cost_price is a derived column, owned by the ingredient editor --
        ## the recipe service deliberately never takes it from a payload (see
        ## recipe_service.py). A seeder that skips this leaves every seeded
        ## recipe costing 0.00, which makes margin_percent meaningless and
        ## hides a badly priced dish until an operator opens it by hand.
        recipe.cost_price = recipe.calculate_cost_from_ingredients()
        db_session.flush()

    print(f"--- Recipes seeded. ({created} created) ---")


def _seed_ingredients(recipe, lines, inventory_by_name):
    """Create this recipe's ingredient lines, skipping ones already present."""
    created = 0

    for line in lines:
        item = inventory_by_name[line["inventory"]]
        exists = db_session.execute(
            select(RecipeIngredient).filter_by(
                recipe_id=recipe.id, inventory_id=item.id, is_deleted=False
            )
        ).scalars().first()

        if exists:
            exists.quantity = Decimal(line["quantity"])
            exists.unit = line["unit"]
            exists.updated_at = datetime.now(timezone.utc)
            continue

        db_session.add(RecipeIngredient(
            recipe_id=recipe.id,
            inventory_id=item.id,
            quantity=Decimal(line["quantity"]),
            unit=line["unit"],
            is_optional=False,
            is_prepped=False,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        created += 1

    return created


def seed_cms_recipes():
    try:
        seed_recipes()
        db_session.commit()
        print("--- Recipes seeded successfully. ---")

    except Exception as exc:
        db_session.rollback()
        print(f"!!! Recipe seeder FAILED: {_safe(str(exc))[:300]}")
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_cms_recipes()