from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.recipe_ingredient_schema import (
    ReplaceRecipeIngredientsSchema,
    UpsertRecipeIngredientSchema,
)
from src.api.services.cms.recipe_ingredient_service import RecipeIngredientService
from src.database.session import db_session


recipe_ingredient_bp = Blueprint("recipe_ingredient", __name__)


class RecipeIngredientRoute:
    def __init__(self, recipe_ingredient_service):
        self.recipe_ingredient_service = recipe_ingredient_service

    def get_recipe_ingredients(self, recipe_id):
        result, status_code = self.recipe_ingredient_service.get_recipe_ingredients(recipe_id)
        return jsonify(result), status_code

    def upsert_ingredient(self, recipe_id):
        payload = request.get_json() or {}
        validated_data = UpsertRecipeIngredientSchema().load(payload)
        result, status_code = self.recipe_ingredient_service.upsert_ingredient(
            recipe_id, validated_data
        )
        return jsonify(result), status_code

    def replace_ingredients(self, recipe_id):
        """The body carries recipe_id for the nested uniqueness check, but the
        path value wins so the URL stays authoritative."""
        payload = request.get_json() or {}
        validated_data = ReplaceRecipeIngredientsSchema().load(payload)
        validated_data["recipe_id"] = recipe_id
        result, status_code = self.recipe_ingredient_service.replace_ingredients(
            recipe_id, validated_data
        )
        return jsonify(result), status_code

    def delete_ingredient(self, recipe_id, ingredient_id):
        result, status_code = self.recipe_ingredient_service.delete_ingredient(
            recipe_id, ingredient_id
        )
        return jsonify(result), status_code

    def check_ingredient_stock(self, recipe_id):
        result, status_code = self.recipe_ingredient_service.check_ingredient_stock(recipe_id)
        return jsonify(result), status_code


recipe_ingredient_service_instance = RecipeIngredientService(db=db_session)
recipe_ingredient_route = RecipeIngredientRoute(
    recipe_ingredient_service=recipe_ingredient_service_instance
)


recipe_ingredient_bp.add_url_rule('/<int:recipe_id>', view_func=requires_module("RECIPE")(recipe_ingredient_route.get_recipe_ingredients), methods=['GET'])
recipe_ingredient_bp.add_url_rule('/<int:recipe_id>/upsert', view_func=requires_module("RECIPE")(recipe_ingredient_route.upsert_ingredient), methods=['POST'])
recipe_ingredient_bp.add_url_rule('/<int:recipe_id>/replace', view_func=requires_module("RECIPE")(recipe_ingredient_route.replace_ingredients), methods=['POST'])
recipe_ingredient_bp.add_url_rule('/<int:recipe_id>/delete/<int:ingredient_id>', view_func=requires_module("RECIPE")(recipe_ingredient_route.delete_ingredient), methods=['POST'])
recipe_ingredient_bp.add_url_rule('/<int:recipe_id>/check-stock', view_func=requires_module("RECIPE")(recipe_ingredient_route.check_ingredient_stock), methods=['GET'])