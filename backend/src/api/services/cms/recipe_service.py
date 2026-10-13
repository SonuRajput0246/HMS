import logging
from decimal import Decimal

from src.api.models.cms.recipe_model import Recipe
from src.api.models.cms.recipe_category_model import RecipeCategory
from src.api.models.cms.recipe_ingredient_model import RecipeIngredient
from src.api.models.common.inventory_model import Inventory
from src.api.services.common.document_sequence_service import DocumentSequenceService
from src.api.utils.enum_helper import EnumHelper, EnumUnavailableError
from src.api.utils.responses import service_response


logger = logging.getLogger(__name__)

STATION_ENUM = "recipe_station"
SPICE_LEVEL_ENUM = "spice_level"


class RecipeService:
    def __init__(self, db):
        self.db = db
        self.sequence_service = DocumentSequenceService(db=db)
        self.enums = EnumHelper(db)

    ## ==================================================================
    ## READS
    ## ==================================================================

    def get_recipes(self, data: dict):
        page_size = data.get("page_size", 20)
        page_number = data.get("page_number", 1)

        query = self.db.query(Recipe).filter(Recipe.is_deleted == False)

        for field in ("category_id", "is_available", "is_vegetarian", "is_recommended"):
            value = data.get(field)
            if value is not None:
                query = query.filter(getattr(Recipe, field) == value)

        if data.get("station"):
            station = self._normalise(data["station"], STATION_ENUM)
            if station is None:
                ## An unknown station filter matches nothing rather than
                ## silently returning the unfiltered menu.
                return service_response(False, "Invalid station filter.", None, 400)
            query = query.filter(Recipe.station == station)

        if data.get("search_value"):
            val = data["search_value"].strip()
            query = query.filter(
                (Recipe.name.like(f"%{val}%")) | (Recipe.recipe_code.like(f"%{val}%"))
            )

        total_records = query.count()
        recipes = (
            query
            .order_by(Recipe.display_order.asc(), Recipe.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        last_page = (total_records + page_size - 1) // page_size
        return {
            "status": True,
            "data": [self._serialize_recipe(r, with_ingredients=False) for r in recipes],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_recipe_by_id(self, recipe_id: int):
        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        return service_response(
            True,
            "Recipe fetched successfully.",
            self._serialize_recipe(recipe, with_ingredients=True),
            200
        )

    def get_menu(self, data: dict):
        """Whole menu grouped by category, for the POS item picker.

        Returns category sections (including an "uncategorised" bucket) so the
        POS can render one screen without a second round trip. Sold-out dishes
        are excluded unless the caller asks for them.
        """
        include_unavailable = data.get("include_unavailable", False)

        query = self.db.query(Recipe).filter(
            Recipe.is_deleted == False,
            Recipe.is_active == True
        )

        if data.get("category_id"):
            query = query.filter(Recipe.category_id == data["category_id"])

        if data.get("station"):
            station = self._normalise(data["station"], STATION_ENUM)
            if station is None:
                return service_response(False, "Invalid station filter.", None, 400)
            query = query.filter(Recipe.station == station)

        if not include_unavailable:
            query = query.filter(Recipe.is_available == True)

        recipes = (
            query
            .order_by(Recipe.display_order.asc(), Recipe.name.asc())
            .all()
        )

        categories = (
            self.db.query(RecipeCategory)
            .filter(RecipeCategory.is_deleted == False, RecipeCategory.is_active == True)
            .order_by(RecipeCategory.display_order.asc(), RecipeCategory.id.asc())
            .all()
        )

        sections = []
        seen_ids = set()

        for category in categories:
            section_recipes = [r for r in recipes if r.category_id == category.id]
            if not section_recipes and not include_unavailable:
                ## Skip empty sections so the POS menu has no dead headers.
                continue
            seen_ids.update(r.id for r in section_recipes)
            sections.append({
                "category_id": category.id,
                "category_name": category.name,
                "category_display_name": category.display_name,
                "display_order": category.display_order,
                "recipes": [self._serialize_recipe(r, with_ingredients=False) for r in section_recipes]
            })

        ## Recipes whose category was deleted or set to an inactive category.
        orphans = [r for r in recipes if r.id not in seen_ids]
        if orphans:
            sections.append({
                "category_id": None,
                "category_name": "uncategorised",
                "category_display_name": "Uncategorised",
                "display_order": 9999,
                "recipes": [self._serialize_recipe(r, with_ingredients=False) for r in orphans]
            })

        return service_response(
            True,
            "Menu fetched successfully.",
            {
                "sections": sections,
                "recipe_count": len(recipes),
                "section_count": len(sections)
            },
            200
        )

    def get_recipe_stations(self):
        """Station list for the KDS screen filter.

        Read through EnumHelper so the options match the dropdown the recipe
        form renders. Enumeration values are returned alongside labels so the
        KDS can group or badge by station without a second lookup.
        """
        try:
            values = self.enums.active_values(STATION_ENUM)
        except EnumUnavailableError as exc:
            ## Infrastructure fault (seeder not run), not bad input. The app
            ## documents this as a 503 so the operator runs the seeder rather
            ## than debugging a client-side validation error.
            logger.exception("RecipeService: enum '%s' unavailable.", STATION_ENUM)
            return service_response(
                False,
                "Kitchen stations are not configured. Run the enum seeder.",
                {"detail": str(exc)},
                503
            )

        return service_response(True, "Stations fetched successfully.", list(values), 200)

    ## ==================================================================
    ## WRITES
    ## ==================================================================

    def upsert_recipe(self, data: dict):
        recipe_id = data["id"]
        name = data["name"]
        is_deleted_op = data.get("is_deleted") is True

        if name and not is_deleted_op:
            duplicate = self.db.query(Recipe).filter(
                Recipe.is_deleted == False,
                Recipe.name == name,
                Recipe.id != recipe_id
            ).first()
            if duplicate:
                return service_response(
                    False,
                    f"A recipe named '{name}' already exists (code {duplicate.recipe_code}).",
                    None, 409
                )

        station = self._normalise(data.get("station") or "other", STATION_ENUM)
        if station is None:
            return service_response(
                False,
                f"'{data.get('station')}' is not a valid kitchen station.",
                None, 400
            )

        spice_level = None
        if data.get("default_spice_level"):
            spice_level = self._normalise(data["default_spice_level"], SPICE_LEVEL_ENUM)
            if spice_level is None:
                return service_response(
                    False,
                    f"'{data['default_spice_level']}' is not a valid spice level.",
                    None, 400
                )

        category_id = data.get("category_id")
        if category_id:
            category = self.db.query(RecipeCategory).filter_by(
                is_deleted=False, id=category_id
            ).first()
            if not category:
                return service_response(False, "Recipe category not found", None, 404)

        if recipe_id == 0:
            required_fields = ("name", "display_name", "selling_price", "is_active")
            for field in required_fields:
                if data.get(field) is None or data.get(field) == "":
                    return service_response(False, f"Field {field} is required.", None, 400)

            recipe = Recipe(recipe_code=self.sequence_service.generate("recipe"))
            self.db.add(recipe)
            message = "Recipe created successfully."
            status_code = 201
        else:
            recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
            if not recipe:
                return service_response(False, "Recipe not found", None, 404)

            message = "Recipe updated successfully."
            status_code = 200

        recipe.name = name
        recipe.display_name = data["display_name"]
        recipe.category_id = category_id
        recipe.description = data.get("description")
        recipe.instructions = data.get("instructions")
        recipe.image_url = data.get("image_url")
        recipe.selling_price = Decimal(str(data["selling_price"]))
        recipe.station = station
        recipe.prep_time_minutes = data.get("prep_time_minutes", 0)
        recipe.cook_time_minutes = data.get("cook_time_minutes", 0)
        recipe.is_vegetarian = data.get("is_vegetarian", False)
        recipe.is_vegan = data.get("is_vegan", False)
        recipe.is_spicy = data.get("is_spicy", False)
        recipe.default_spice_level = spice_level
        recipe.is_recommended = data.get("is_recommended", False)
        recipe.is_available = data.get("is_available", True)
        recipe.display_order = data.get("display_order", 0)
        recipe.is_active = data["is_active"]

        ## cost_price is never taken from the payload -- it is owned by the
        ## ingredient editor. On create there are no ingredients yet, so it
        ## stays at the column default; the ingredient service restates it.
        if is_deleted_op:
            recipe.is_deleted = True
            recipe.is_active = False
            ## Stop selling immediately, not just hide it from the admin list.
            recipe.is_available = False
            message = "Recipe deleted successfully."

        self.db.commit()
        self.db.refresh(recipe)

        return service_response(
            True, message, self._serialize_recipe(recipe, with_ingredients=True), status_code
        )

    def update_availability(self, data: dict):
        """86 / un-86 a dish without opening the full editor."""
        recipe_id = data["id"]

        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        recipe.is_available = data["is_available"]
        self.db.commit()
        self.db.refresh(recipe)

        message = (
            "Recipe marked as available."
            if recipe.is_available
            else "Recipe marked as unavailable."
        )
        return service_response(
            True, message, self._serialize_recipe(recipe, with_ingredients=False), 200
        )

    ## ==================================================================
    ## internals
    ## ==================================================================

    def _normalise(self, value, enum_key: str):
        """Value for an enum-backed string column, or None when not allowed.

        EnumUnavailableError is caught and turned into a logged None so an
        unseeded enum table surfaces as a 400 on the write path rather than an
        unhandled 500. The seeder is the fix, and the log says so.
        """
        try:
            return self.enums.normalise(value, enum_key)
        except EnumUnavailableError:
            logger.exception("RecipeService: enum '%s' unavailable.", enum_key)
            return None

    def _serialize_recipe(self, recipe: Recipe, with_ingredients: bool = False) -> dict:
        payload = {
            "id": recipe.id,
            "recipe_code": recipe.recipe_code,
            "name": recipe.name,
            "display_name": recipe.display_name,
            "category_id": recipe.category_id,
            "category_name": recipe.category.name if recipe.category else None,
            "category_display_name": recipe.category.display_name if recipe.category else None,
            "description": recipe.description,
            "image_url": recipe.image_url,
            "selling_price": str(recipe.selling_price),
            "cost_price": str(recipe.cost_price),
            "margin_percent": str(recipe.margin_percent()),
            "station": recipe.station,
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "total_time_minutes": recipe.total_time(),
            "is_vegetarian": recipe.is_vegetarian,
            "is_vegan": recipe.is_vegan,
            "is_spicy": recipe.is_spicy,
            "default_spice_level": recipe.default_spice_level,
            "is_recommended": recipe.is_recommended,
            "is_available": recipe.is_available,
            "display_order": recipe.display_order,
            "is_active": recipe.is_active,
            "is_profitable": recipe.is_profitable(),
            "can_be_ordered": recipe.can_be_ordered()
        }

        if with_ingredients:
            payload["instructions"] = recipe.instructions
            live_lines = [i for i in recipe.ingredients if not i.is_deleted]
            payload["ingredients"] = [
                {
                    "id": i.id,
                    "inventory_id": i.inventory_id,
                    "inventory_name": i.inventory_item.name if i.inventory_item else None,
                    "quantity": str(i.quantity),
                    "unit": i.unit,
                    "is_optional": i.is_optional,
                    "is_prepped": i.is_prepped,
                    "line_cost": str(i.total_cost()),
                    "in_stock": i.is_stock_available() if i.inventory_item else False
                }
                for i in live_lines
            ]
            payload["ingredient_count"] = len(live_lines)

            ## Portions currently makeable = lowest ratio across mandatory
            ## ingredient lines. Computed here too so the recipe editor can warn
            ## "only 3 portions left" without a separate call.
            payload["portions_available"] = self._portions_available(live_lines)

        return payload

    def _portions_available(self, lines):
        """How many portions current stock supports, or None if unbounded.

        Optional lines are skipped: a missing garnish should not mark a dish
        unsellable.
        """
        portions = None
        for line in lines:
            if line.is_optional or line.inventory_item is None:
                continue
            needed = Decimal(str(line.quantity))
            if needed <= 0:
                continue
            available = Decimal(str(line.inventory_item.quantity))
            possible = int(available / needed)
            portions = possible if portions is None else min(portions, possible)
        return portions