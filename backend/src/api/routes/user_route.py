from src.database.session import db_session
from flask import request, jsonify, Blueprint
from src.api.services.user_service import UserService
from src.api.middlewares.authorization import requires_module
from src.api.schemas.pagination_schema import PaginationSchema
from src.api.schemas.user_schema import GetUserByIdSchema, UpsertUserSchema

user_bp = Blueprint('user', __name__)

class UserRoute:
    def __init__(self, user_service):
        self.user_service = user_service


    def get_users(self):
        payload = request.get_json() or {}
        validated_data = PaginationSchema().load(payload)
        result, status_code = self.user_service.get_users(validated_data)
        return jsonify(result), status_code

    def get_user_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetUserByIdSchema().load(payload)
        result, status_code = self.user_service.get_user_by_id(validated_data["id"])
        return jsonify(result), status_code


    def upsert_user(self):
        payload = request.get_json() or {}
        validated_data = UpsertUserSchema().load(payload)
        result, status_code = self.user_service.upsert_user(validated_data)
        return jsonify(result), status_code



user_service_instance = UserService(db=db_session)
user_route = UserRoute(user_service=user_service_instance)
user_bp.add_url_rule('/get', view_func=requires_module("USER_MANAGEMENT")(user_route.get_users), methods=['POST'])
user_bp.add_url_rule('/get-by-id', view_func=requires_module("USER_MANAGEMENT")(user_route.get_user_by_id), methods=['GET'])
user_bp.add_url_rule('/upsert', view_func=requires_module("USER_MANAGEMENT")(user_route.upsert_user), methods=['POST'])