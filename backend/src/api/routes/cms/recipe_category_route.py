from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.recipe_category_schema import (
    GetRecipeCategoriesSchema,
    GetRecipeCategoryByIdSchema,
    UpsertRecipeCategorySchema,
)
from src.api.services.cms.recipe_category_service import RecipeCategoryService
from src.database.session import db_session


recipe_category_bp = Blueprint("recipe_category", __name__)


class RecipeCategoryRoute:
    def __init__(self, recipe_category_service):
        self.recipe_category_service = recipe_category_service

    def get_recipe_categories(self):
        payload = request.get_json() or {}
        validated_data = GetRecipeCategoriesSchema().load(payload)
        result, status_code = self.recipe_category_service.get_recipe_categories(validated_data)
        return jsonify(result), status_code

    def get_recipe_category_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetRecipeCategoryByIdSchema().load(payload)
        result, status_code = self.recipe_category_service.get_recipe_category_by_id(
            validated_data["id"]
        )
        return jsonify(result), status_code

    def upsert_recipe_category(self):
        payload = request.get_json() or {}
        validated_data = UpsertRecipeCategorySchema().load(payload)
        result, status_code = self.recipe_category_service.upsert_recipe_category(validated_data)
        return jsonify(result), status_code

    def get_category_recipe_count(self):
        payload = request.args.to_dict()
        validated_data = GetRecipeCategoryByIdSchema().load(payload)
        result, status_code = self.recipe_category_service.get_category_recipe_count(
            validated_data["id"]
        )
        return jsonify(result), status_code


recipe_category_service_instance = RecipeCategoryService(db=db_session)
recipe_category_route = RecipeCategoryRoute(
    recipe_category_service=recipe_category_service_instance
)


recipe_category_bp.add_url_rule('/get', view_func=requires_module("RECIPE")(recipe_category_route.get_recipe_categories), methods=['POST'])
recipe_category_bp.add_url_rule('/get-by-id', view_func=requires_module("RECIPE")(recipe_category_route.get_recipe_category_by_id), methods=['GET'])
recipe_category_bp.add_url_rule('/upsert', view_func=requires_module("RECIPE")(recipe_category_route.upsert_recipe_category), methods=['POST'])
recipe_category_bp.add_url_rule('/get-recipe-count', view_func=requires_module("RECIPE")(recipe_category_route.get_category_recipe_count), methods=['GET'])