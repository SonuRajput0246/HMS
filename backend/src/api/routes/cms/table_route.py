from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.table_schema import (
    GetTableByIdSchema,
    GetTablesSchema,
    UpsertTableSchema,
    UpsertTableStatusSchema,
)
from src.api.services.cms.table_service import TableService
from src.database.session import db_session


table_bp = Blueprint("table", __name__)


class TableRoute:
    def __init__(self, table_service):
        self.table_service = table_service

    def get_tables(self):
        payload = request.get_json() or {}
        validated_data = GetTablesSchema().load(payload)
        result, status_code = self.table_service.get_tables(validated_data)
        return jsonify(result), status_code

    def get_table_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetTableByIdSchema().load(payload)
        result, status_code = self.table_service.get_table_by_id(validated_data["id"])
        return jsonify(result), status_code

    def get_table_floor_view(self):
        result, status_code = self.table_service.get_table_floor_view()
        return jsonify(result), status_code

    def upsert_table(self):
        payload = request.get_json() or {}
        validated_data = UpsertTableSchema().load(payload)
        result, status_code = self.table_service.upsert_table(validated_data)
        return jsonify(result), status_code

    def update_table_status(self):
        payload = request.get_json() or {}
        validated_data = UpsertTableStatusSchema().load(payload)
        result, status_code = self.table_service.update_table_status(validated_data)
        return jsonify(result), status_code


table_service_instance = TableService(db=db_session)
table_route = TableRoute(table_service=table_service_instance)


table_bp.add_url_rule('/get', view_func=requires_module("TABLE")(table_route.get_tables), methods=['POST'])
table_bp.add_url_rule('/get-by-id', view_func=requires_module("TABLE")(table_route.get_table_by_id), methods=['GET'])
table_bp.add_url_rule('/get-floor-view', view_func=requires_module("TABLE")(table_route.get_table_floor_view), methods=['GET'])
table_bp.add_url_rule('/upsert', view_func=requires_module("TABLE")(table_route.upsert_table), methods=['POST'])
table_bp.add_url_rule('/update-status', view_func=requires_module("TABLE")(table_route.update_table_status), methods=['POST'])