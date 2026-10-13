from flask import request, jsonify, Blueprint
from src.api.middlewares.authorization import requires_module
from src.api.schemas.pagination_schema import PaginationSchema
from src.api.schemas.inventory_schema import GetCategoryByIdSchema, GetInventoryById, UpsertInventoryCategorySchema, \
    UpsertInventorySchema
from src.api.services.inventory_service import InventoryService
from src.database.session import db_session

inventory_bp = Blueprint('inventory', __name__)


class InventoryRoute:
    def __init__(self, inventory_service):
        self.inventory_service = inventory_service


    def get_inventory_categories(self):
        payload = request.get_json() or {}
        validated_data = PaginationSchema().load(payload)
        result, status_code = self.inventory_service.get_inventory_categories(validated_data)
        return jsonify(result), status_code

    def get_inventory_category_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetCategoryByIdSchema().load(payload)
        result, status_code = self.inventory_service.get_inventory_category_by_id(validated_data["id"])
        return jsonify(result), status_code

    def upsert_inventory_category(self):
        payload = request.get_json() or {}
        validated_data = UpsertInventoryCategorySchema().load(payload)
        result, status_code = self.inventory_service.upsert_inventory_category(validated_data)
        return jsonify(result), status_code

    def get_inventories(self):
        payload = request.get_json() or {}
        validated_data = PaginationSchema().load(payload)
        result, status_code = self.inventory_service.get_inventories(validated_data)
        return jsonify(result), status_code

    def get_inventory_units(self):
        result, status_code = self.inventory_service.get_inventory_units()
        return jsonify(result), status_code


    def get_inventory_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetInventoryById().load(payload)
        result, status_code = self.inventory_service.get_inventory_by_id(validated_data["id"])
        return jsonify(result), status_code

    def upsert_inventory(self):
        payload = request.get_json() or {}
        validated_data = UpsertInventorySchema().load(payload)
        result, status_code = self.inventory_service.upsert_inventory(validated_data)
        return jsonify(result), status_code




inventory_service_instance = InventoryService(db=db_session)
inventory_route = InventoryRoute(inventory_service=inventory_service_instance)

inventory_bp.add_url_rule('/get-categories', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.get_inventory_categories), methods=['POST'])
inventory_bp.add_url_rule('/get-category-by-id', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.get_inventory_category_by_id), methods=['GET'])
inventory_bp.add_url_rule('/upsert-category', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.upsert_inventory_category), methods=['POST'])
inventory_bp.add_url_rule('/get', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.get_inventories), methods=['POST'])
inventory_bp.add_url_rule('/get-units', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.get_inventory_units), methods=['GET'])
inventory_bp.add_url_rule('/get-by-id', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.get_inventory_by_id), methods=['GET'])
inventory_bp.add_url_rule('/upsert', view_func=requires_module("INVENTORY_MANAGEMENT")(inventory_route.upsert_inventory), methods=['POST'])