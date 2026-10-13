from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.recipe_schema import (
    GetMenuSchema,
    GetRecipeByIdSchema,
    GetRecipesSchema,
    UpdateRecipeAvailabilitySchema,
    UpsertRecipeSchema,
)
from src.api.services.cms.recipe_service import RecipeService
from src.database.session import db_session


recipe_bp = Blueprint("recipe", __name__)


class RecipeRoute:
    def __init__(self, recipe_service):
        self.recipe_service = recipe_service

    def get_recipes(self):
        payload = request.get_json() or {}
        validated_data = GetRecipesSchema().load(payload)
        result, status_code = self.recipe_service.get_recipes(validated_data)
        return jsonify(result), status_code

    def get_recipe_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetRecipeByIdSchema().load(payload)
        result, status_code = self.recipe_service.get_recipe_by_id(validated_data["id"])
        return jsonify(result), status_code

    def get_menu(self):
        payload = request.get_json() or {}
        validated_data = GetMenuSchema().load(payload)
        result, status_code = self.recipe_service.get_menu(validated_data)
        return jsonify(result), status_code

    def get_recipe_stations(self):
        result, status_code = self.recipe_service.get_recipe_stations()
        return jsonify(result), status_code

    def upsert_recipe(self):
        payload = request.get_json() or {}
        validated_data = UpsertRecipeSchema().load(payload)
        result, status_code = self.recipe_service.upsert_recipe(validated_data)
        return jsonify(result), status_code

    def update_availability(self):
        payload = request.get_json() or {}
        validated_data = UpdateRecipeAvailabilitySchema().load(payload)
        result, status_code = self.recipe_service.update_availability(validated_data)
        return jsonify(result), status_code


recipe_service_instance = RecipeService(db=db_session)
recipe_route = RecipeRoute(recipe_service=recipe_service_instance)


recipe_bp.add_url_rule('/get', view_func=requires_module("RECIPE")(recipe_route.get_recipes), methods=['POST'])
recipe_bp.add_url_rule('/get-by-id', view_func=requires_module("RECIPE")(recipe_route.get_recipe_by_id), methods=['GET'])
recipe_bp.add_url_rule('/get-menu', view_func=requires_module("RECIPE")(recipe_route.get_menu), methods=['POST'])
recipe_bp.add_url_rule('/get-stations', view_func=requires_module("RECIPE")(recipe_route.get_recipe_stations), methods=['GET'])
recipe_bp.add_url_rule('/upsert', view_func=requires_module("RECIPE")(recipe_route.upsert_recipe), methods=['POST'])
recipe_bp.add_url_rule('/update-availability', view_func=requires_module("RECIPE")(recipe_route.update_availability), methods=['POST'])