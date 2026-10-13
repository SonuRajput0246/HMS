from decimal import Decimal

from src.api.models.cms.recipe_model import Recipe
from src.api.models.cms.recipe_ingredient_model import RecipeIngredient
from src.api.models.common.inventory_model import Inventory
from src.api.utils.responses import service_response


class RecipeIngredientService:
    def __init__(self, db):
        self.db = db

    def get_recipe_ingredients(self, recipe_id: int):
        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        return service_response(
            True,
            "Ingredients fetched successfully.",
            [self._serialize_ingredient(i) for i in recipe.ingredients if not i.is_deleted],
            200
        )

    def upsert_ingredient(self, recipe_id: int, data: dict):
        """Add or edit a single ingredient line, then restate the recipe cost."""
        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        inventory = self._resolve_inventory(data["inventory_id"])
        if isinstance(inventory, tuple):
            return inventory

        ingredient_id = data["id"]

        if ingredient_id == 0:
            ## Check for a duplicate line before insert; the DB unique
            ## constraint would otherwise raise a raw IntegrityError.
            existing = self.db.query(RecipeIngredient).filter_by(
                is_deleted=False, recipe_id=recipe.id, inventory_id=inventory.id
            ).first()
            if existing:
                return service_response(
                    False,
                    f"'{inventory.name}' is already an ingredient of this recipe. Edit the existing line instead.",
                    {"ingredient_id": existing.id},
                    409
                )

            ingredient = RecipeIngredient(recipe_id=recipe.id)
            self.db.add(ingredient)
            message = "Ingredient added successfully."
            status_code = 201
        else:
            ingredient = self.db.query(RecipeIngredient).filter_by(
                is_deleted=False, id=ingredient_id, recipe_id=recipe.id
            ).first()
            if not ingredient:
                return service_response(False, "Recipe ingredient not found", None, 404)

            ## Swapping the inventory item on an existing line could collide
            ## with another line that already holds that item.
            if data["inventory_id"] != ingredient.inventory_id:
                clash = self.db.query(RecipeIngredient).filter_by(
                    is_deleted=False, recipe_id=recipe.id, inventory_id=data["inventory_id"]
                ).first()
                if clash:
                    return service_response(
                        False,
                        "Another ingredient line already uses this inventory item.",
                        None, 409
                    )

            message = "Ingredient updated successfully."
            status_code = 200

        ingredient.inventory_id = inventory.id
        ingredient.quantity = Decimal(str(data["quantity"]))
        ingredient.unit = data["unit"]
        ingredient.is_optional = data.get("is_optional", False)
        ingredient.is_prepped = data.get("is_prepped", False)

        self.db.flush()
        self.db.refresh(recipe)
        self._restate_recipe_cost(recipe)

        self.db.commit()
        self.db.refresh(recipe)

        return service_response(
            True,
            message,
            {
                "ingredient": self._serialize_ingredient(ingredient),
                "cost_price": str(recipe.cost_price),
                "margin_percent": str(recipe.margin_percent())
            },
            status_code
        )

    def replace_ingredients(self, recipe_id: int, data: dict):
        """Replace the whole ingredient list from the editor grid.

        Existing live lines are matched by inventory_id: a line whose
        inventory_id is still present is updated in place (keeping its id, so
        the grid stays stable), a line whose inventory_id is absent is soft
        deleted, and an inventory_id with no existing line becomes a new row.
        """
        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        payload_rows = data["ingredients"]

        ## Resolve every inventory id up front so a bad id fails the whole
        ## request before anything is written.
        resolved = {}
        for idx, row in enumerate(payload_rows):
            inventory = self._resolve_inventory(row["inventory_id"])
            if isinstance(inventory, tuple):
                return inventory
            resolved[inventory.id] = inventory

        existing_lines = {
            ing.inventory_id: ing
            for ing in self.db.query(RecipeIngredient).filter_by(
                is_deleted=False, recipe_id=recipe.id
            ).all()
        }

        added = 0
        updated = 0
        removed = 0

        for row in payload_rows:
            inv_id = row["inventory_id"]
            inventory = resolved[inv_id]
            line = existing_lines.get(inv_id)

            if line is None:
                line = RecipeIngredient(
                    recipe_id=recipe.id,
                    inventory_id=inventory.id
                )
                self.db.add(line)
                added += 1
            else:
                updated += 1

            line.quantity = Decimal(str(row["quantity"]))
            line.unit = row["unit"]
            line.is_optional = row.get("is_optional", False)
            line.is_prepped = row.get("is_prepped", False)

        ## Lines dropped from the grid are removed outright rather than soft
        ## deleted -- see delete_ingredient() for why the
        ## UNIQUE(recipe_id, inventory_id) constraint rules out keeping the row.
        for inv_id, line in existing_lines.items():
            if inv_id not in resolved:
                self.db.delete(line)
                removed += 1

        self.db.flush()
        self.db.refresh(recipe)
        self._restate_recipe_cost(recipe)

        self.db.commit()
        self.db.refresh(recipe)

        return service_response(
            True,
            "Ingredients saved successfully.",
            {
                "recipe_id": recipe.id,
                "added": added,
                "updated": updated,
                "removed": removed,
                "cost_price": str(recipe.cost_price),
                "margin_percent": str(recipe.margin_percent()),
                "ingredients": [
                    self._serialize_ingredient(i)
                    for i in self.db.query(RecipeIngredient).filter_by(
                        is_deleted=False, recipe_id=recipe.id
                    ).order_by(RecipeIngredient.id.asc()).all()
                ]
            },
            200
        )

    def delete_ingredient(self, recipe_id: int, ingredient_id: int):
        """Remove one line, then restate the recipe cost.

        HARD delete, unlike every other CMS entity. recipe_ingredients carries
        a plain UNIQUE(recipe_id, inventory_id) constraint and MySQL cannot make
        that partial, so a soft-deleted row keeps holding the key and
        re-adding that ingredient to the same recipe later fails with
        IntegrityError 1062. These lines are a child collection owned entirely
        by the recipe and have no standalone audit value -- the record that
        matters lives in cms_order_items, which is denormalised (item_name and
        unit_price copied at order time) and so survives a recipe edit anyway.
        """
        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        ingredient = self.db.query(RecipeIngredient).filter_by(
            is_deleted=False, id=ingredient_id, recipe_id=recipe.id
        ).first()
        if not ingredient:
            return service_response(False, "Recipe ingredient not found", None, 404)

        self.db.delete(ingredient)
        self.db.flush()
        self.db.refresh(recipe)
        self._restate_recipe_cost(recipe)

        self.db.commit()
        self.db.refresh(recipe)

        return service_response(
            True,
            "Ingredient deleted successfully.",
            {"cost_price": str(recipe.cost_price), "margin_percent": str(recipe.margin_percent())},
            200
        )

    def check_ingredient_stock(self, recipe_id: int):
        """Can this recipe actually be made right now?

        Reports the worst-case quantity available across all ingredient lines
        (how many portions could be produced from current stock) plus the
        specific lines that are short. The POS uses this to grey out a dish
        instead of letting a guest order something the kitchen cannot plate.
        """
        recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=recipe_id).first()
        if not recipe:
            return service_response(False, "Recipe not found", None, 404)

        lines = [i for i in recipe.ingredients if not i.is_deleted]
        if not lines:
            ## No ingredient lines means nothing to verify. Treat as makeable
            ## rather than blocking a dish that is simply sold as-is.
            return service_response(
                True, "Stock checked successfully.",
                {"recipe_id": recipe.id, "is_makeable": True, "portions_available": None, "short_items": []},
                200
            )

        short_items = []
        portions = None

        for line in lines:
            inventory = line.inventory_item
            if inventory is None:
                continue

            available = Decimal(str(inventory.quantity))
            needed = Decimal(str(line.quantity))

            if needed <= 0:
                continue

            if line.is_optional:
                ## An optional garnish never blocks the dish.
                continue

            possible = int(available / needed)
            portions = possible if portions is None else min(portions, possible)

            if available < needed:
                short_items.append({
                    "inventory_id": inventory.id,
                    "inventory_name": inventory.name,
                    "required": str(needed),
                    "available": str(available),
                    "unit": line.unit
                })

        return service_response(
            True, "Stock checked successfully.",
            {
                "recipe_id": recipe.id,
                "is_makeable": not short_items,
                "portions_available": portions if portions is not None else 0,
                "short_items": short_items
            },
            200
        )

    ## ------------------------------------------------------------------
    ## internals
    ## ------------------------------------------------------------------

    def _resolve_inventory(self, inventory_id: int):
        """Fetch an active inventory item, or return a ready-made error tuple."""
        inventory = self.db.query(Inventory).filter_by(is_deleted=False, id=inventory_id).first()
        if not inventory:
            return service_response(False, "Inventory item not found", None, 404)

        if not inventory.is_active:
            return service_response(
                False,
                f"Inventory item '{inventory.name}' is inactive and cannot be used in a recipe.",
                None, 409
            )

        return inventory

    def _restate_recipe_cost(self, recipe: Recipe) -> None:
        """Recompute cost_price after any ingredient change.

        Reloads the ingredient collection first: a line inserted or
        soft-deleted during this request is not reflected in the already-loaded
        `recipe.ingredients` until it is expired.
        """
        self.db.expire(recipe, ["ingredients"])
        recipe.update_cost_price()

    def _serialize_ingredient(self, ingredient: RecipeIngredient) -> dict:
        inventory = ingredient.inventory_item
        return {
            "id": ingredient.id,
            "recipe_id": ingredient.recipe_id,
            "inventory_id": ingredient.inventory_id,
            "inventory_name": inventory.name if inventory else None,
            "inventory_unit": inventory.unit if inventory else None,
            "quantity": str(ingredient.quantity),
            "unit": ingredient.unit,
            "is_optional": ingredient.is_optional,
            "is_prepped": ingredient.is_prepped,
            "line_cost": str(ingredient.total_cost()),
            "unit_cost": str(inventory.unit_cost) if inventory and inventory.unit_cost is not None else None,
            "in_stock": ingredient.is_stock_available() if inventory else False
        }