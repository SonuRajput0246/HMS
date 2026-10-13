from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.table_zone_schema import (
    GetTableZoneByIdSchema,
    UpsertTableZoneSchema,
)
from src.api.schemas.common.pagination_schema import PaginationSchema
from src.api.services.cms.table_zone_service import TableZoneService
from src.database.session import db_session


table_zone_bp = Blueprint("table_zone", __name__)


class TableZoneRoute:
    def __init__(self, table_zone_service):
        self.table_zone_service = table_zone_service

    def get_table_zones(self):
        payload = request.get_json() or {}
        validated_data = PaginationSchema().load(payload)
        result, status_code = self.table_zone_service.get_table_zones(validated_data)
        return jsonify(result), status_code

    def get_table_zone_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetTableZoneByIdSchema().load(payload)
        result, status_code = self.table_zone_service.get_table_zone_by_id(validated_data["id"])
        return jsonify(result), status_code

    def upsert_table_zone(self):
        payload = request.get_json() or {}
        validated_data = UpsertTableZoneSchema().load(payload)
        result, status_code = self.table_zone_service.upsert_table_zone(validated_data)
        return jsonify(result), status_code

    def get_zone_table_count(self):
        payload = request.args.to_dict()
        validated_data = GetTableZoneByIdSchema().load(payload)
        result, status_code = self.table_zone_service.get_zone_table_count(validated_data["id"])
        return jsonify(result), status_code


table_zone_service_instance = TableZoneService(db=db_session)
table_zone_route = TableZoneRoute(table_zone_service=table_zone_service_instance)


table_zone_bp.add_url_rule('/get', view_func=requires_module("TABLE")(table_zone_route.get_table_zones), methods=['POST'])
table_zone_bp.add_url_rule('/get-by-id', view_func=requires_module("TABLE")(table_zone_route.get_table_zone_by_id), methods=['GET'])
table_zone_bp.add_url_rule('/upsert', view_func=requires_module("TABLE")(table_zone_route.upsert_table_zone), methods=['POST'])
table_zone_bp.add_url_rule('/get-table-count', view_func=requires_module("TABLE")(table_zone_route.get_zone_table_count), methods=['GET'])