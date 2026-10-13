from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.common.pagination_schema import PaginationSchema
from src.api.schemas.common.role_schema import GetRoleByIdSchema, UpsertRoleSchema, UpdateRoleAccessSchema
from src.api.services.common.admin_service import AdminService
from src.database.session import db_session

admin_bp = Blueprint('admin', __name__)


class AdminRoute:
    def __init__(self, admin_service):
        self.admin_service = admin_service

    def get_roles(self):
        payload = request.get_json() or {}
        validated_data = PaginationSchema().load(payload)
        result, status_code = self.admin_service.get_roles(validated_data)
        return jsonify(result), status_code

    def get_role_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetRoleByIdSchema().load(payload)
        result, status_code = self.admin_service.get_role_by_id(validated_data["id"])
        return jsonify(result), status_code

    def upsert_role(self):
        payload = request.get_json() or {}
        validated_data = UpsertRoleSchema().load(payload)
        result, status_code = self.admin_service.upsert_role(validated_data)
        return jsonify(result), status_code

    def get_all_modules(self):
        result, status_code = self.admin_service.get_all_modules()
        return jsonify(result), status_code

    def update_role_access(self):
        payload = request.get_json() or {}
        validated_data = UpdateRoleAccessSchema().load(payload)
        result, status_code = self.admin_service.update_role_access(validated_data)
        return jsonify(result), status_code



admin_service_instance = AdminService(db=db_session)
admin_route = AdminRoute(admin_service=admin_service_instance)

admin_bp.add_url_rule('/get-roles', view_func=requires_module("ROLE")(admin_route.get_roles), methods=['POST'])
admin_bp.add_url_rule('/get-role-by-id', view_func=requires_module("ROLE")(admin_route.get_role_by_id), methods=['GET'])
admin_bp.add_url_rule('/upsert-role', view_func=requires_module("ROLE")(admin_route.upsert_role), methods=['POST'])
admin_bp.add_url_rule('/get-modules', view_func=requires_module("ROLE")(admin_route.get_all_modules), methods=['GET'])
admin_bp.add_url_rule('/update-role-access', view_func=requires_module("ROLE")(admin_route.update_role_access), methods=['POST'])