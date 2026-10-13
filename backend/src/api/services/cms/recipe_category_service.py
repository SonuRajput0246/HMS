from src.api.models.cms.recipe_category_model import RecipeCategory
from src.api.models.cms.recipe_model import Recipe
from src.api.services.cms.reference_data_helper import revive_or_flag_duplicate
from src.api.utils.responses import service_response


class RecipeCategoryService:
    def __init__(self, db):
        self.db = db

    def get_recipe_categories(self, data: dict):
        page_size = data.get("page_size", 100)
        page_number = data.get("page_number", 1)
        search_value = data.get("search_value")

        query = self.db.query(RecipeCategory).filter(RecipeCategory.is_deleted == False)

        if search_value:
            val = search_value.strip()
            query = query.filter(RecipeCategory.name.like(f"{val}%"))

        total_records = query.count()
        categories = (
            query
            .order_by(RecipeCategory.display_order.asc(), RecipeCategory.id.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        last_page = (total_records + page_size - 1) // page_size
        return {
            "status": True,
            "data": [self._serialize_category(c, with_counts=True) for c in categories],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_recipe_category_by_id(self, category_id: int):
        category = self.db.query(RecipeCategory).filter_by(is_deleted=False, id=category_id).first()
        if not category:
            return service_response(False, "Recipe category not found", None, 404)

        return service_response(
            True,
            "Recipe category fetched successfully.",
            self._serialize_category(category, with_counts=True),
            200
        )

    def upsert_recipe_category(self, data: dict):
        category_id = data["id"]
        category_name = data["name"]
        is_deleted_op = data.get("is_deleted") is True

        if category_name and not is_deleted_op:
            duplicate = self.db.query(RecipeCategory).filter(
                RecipeCategory.is_deleted == False,
                RecipeCategory.name == category_name,
                RecipeCategory.id != category_id
            ).first()
            if duplicate:
                return service_response(
                    False, "Recipe category with this name already exists.", None, 409
                )

        if category_id == 0:
            required_fields = ("name", "display_name", "is_active")
            for field in required_fields:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required.", None, 400)

            ## A category with this name may exist as a soft-deleted row. UNIQUE
            ## on `name` is not partial in MySQL, so inserting afresh would
            ## fail with IntegrityError 1062 -- which is exactly what happens if
            ## an operator deletes "Desserts" and later re-adds it. Revive the
            ## old row instead, keeping its id so its recipes come back too.
            tombstone, taken = revive_or_flag_duplicate(
                self.db, RecipeCategory, category_name, category_id
            )
            if taken:
                return service_response(
                    False, "Recipe category with this name already exists.", None, 409
                )

            if tombstone is not None:
                category = tombstone
                category.is_deleted = False
                category.deleted_at = None
                message = "Recipe category restored successfully."
            else:
                category = RecipeCategory()
                self.db.add(category)
                message = "Recipe category created successfully."

            status_code = 201
        else:
            category = self.db.query(RecipeCategory).filter_by(is_deleted=False, id=category_id).first()
            if not category:
                return service_response(False, "Recipe category not found", None, 404)

            message = "Recipe category updated successfully."
            status_code = 200

        fields = (
            "name", "display_name", "description",
            "display_order", "is_active", "is_deleted"
        )
        for field in fields:
            if field in data:
                setattr(category, field, data[field])

        ## Deleting a category leaves its recipes uncategorized rather than
        ## deleting them -- the recipe -> category_id FK is ON DELETE SET NULL,
        ## so the menu items survive and simply move to "Uncategorised" on the
        ## POS menu. That is recoverable; silently deleting sellable menu items
        ## is not.
        if is_deleted_op:
            category.is_deleted = True
            category.is_active = False
            message = "Recipe category deleted successfully."

        self.db.commit()
        self.db.refresh(category)

        return service_response(
            True, message, self._serialize_category(category, with_counts=True), status_code
        )

    def get_category_recipe_count(self, category_id: int):
        """Lets the category screen warn how many menu items will be orphaned
        before the operator deletes a category."""
        category = self.db.query(RecipeCategory).filter_by(is_deleted=False, id=category_id).first()
        if not category:
            return service_response(False, "Recipe category not found", None, 404)

        count = self.db.query(Recipe).filter(
            Recipe.is_deleted == False,
            Recipe.category_id == category_id
        ).count()

        return service_response(
            True, "Fetched recipe count successfully.", {"recipe_count": count}, 200
        )

    def _serialize_category(self, category: RecipeCategory, with_counts: bool = False) -> dict:
        payload = {
            "id": category.id,
            "name": category.name,
            "display_name": category.display_name,
            "description": category.description,
            "display_order": category.display_order,
            "is_active": category.is_active
        }
        if with_counts:
            ## Two small counts per category instead of a lazy load per row.
            payload["recipe_count"] = sum(
                1 for r in category.recipes if not r.is_deleted
            )
            payload["available_recipe_count"] = sum(
                1 for r in category.recipes
                if not r.is_deleted and r.is_available and r.is_active
            )
        return payload