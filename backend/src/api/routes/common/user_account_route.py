import logging
from flask import Blueprint, request, jsonify, make_response, current_app
from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.common.user_account_schema import UpdateUserProfileSchema, DeleteMyAccountSchema, \
    DeactivateMyAccountSchema, UpdatePasswordSchema
from src.api.services.common.user_account_service import UserAccountService
from src.api.utils.jwt_helper import get_user_id_from_jwt
from src.database.session import db_session

account_bp = Blueprint('account', __name__)

class UserAccountRoute:
    def __init__(self, user_account_service):
        self.account_service = user_account_service

    def update_user_profile(self):
        payload = request.get_json() or {}
        user_id = get_user_id_from_jwt()
        validated_data = UpdateUserProfileSchema().load(payload)
        result, status_code = self.account_service.update_user_profile(user_id, validated_data)
        return jsonify(result), status_code

    def update_password(self):
            payload = request.get_json()
            validated_data = UpdatePasswordSchema().load(payload)
            user_id = get_user_id_from_jwt()
            result, status_code = self.account_service.update_user_password(user_id, validated_data)
            return jsonify(result), status_code

    def deactivate_user(self):
        try:
            payload = request.get_json() or {}
            user_id = get_user_id_from_jwt()
            validated_data = DeactivateMyAccountSchema().load(payload)
            result = self.account_service.deactivate_user(user_id, validated_data)
            if "error" in result:
                return jsonify({"status": False, "message": result["error"]}), result["code"]

            response = make_response(
                jsonify({"status": True, "message": "Your account has been deactivated."}),
                200
            )
            response.delete_cookie(
                key="hms_refreshToken",
                httponly=True,
                secure=current_app.config["COOKIE_SECURE"],
                samesite=current_app.config["COOKIE_SAMESITE"],
                path="/"
            )
            return response
        except Exception as e:
            self.account_service.db.rollback()
            logging.error(f"Deactivation Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500

    def delete_my_account(self):
        try:
            payload = request.get_json() or {}
            user_id = get_user_id_from_jwt()
            validated_data = DeleteMyAccountSchema().load(payload)
            result = self.account_service.delete_my_account(user_id, validated_data)
            if "error" in result:
                return jsonify({"status": False, "message": result["error"]}), result["code"]

            if result["revoke_session"]:
                response = make_response(
                    jsonify({"status": True, "message": "Your account has been deleted successfully."}),
                    200
                )
                response.delete_cookie(
                    key="hms_refreshToken",
                    httponly=True,
                    secure=current_app.config["COOKIE_SECURE"],
                    samesite=current_app.config["COOKIE_SAMESITE"],
                    path="/"
                )
                return response
            else:
                return jsonify({"status": True, "message": "You have active reservation. Your account deletion request has been registered."}), 200
        except Exception as e:
            self.account_service.db.rollback()
            logging.error(f"Delete My Account Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500

user_account_service_instance = UserAccountService(db=db_session)
account_route = UserAccountRoute(user_account_service=user_account_service_instance)

## Register routes to blueprint using class methods
account_bp.add_url_rule('/deactivate', view_func=requires_module(SELF_SERVICE)(account_route.deactivate_user), methods=['POST'])
account_bp.add_url_rule('/update-profile', view_func=requires_module(SELF_SERVICE)(account_route.update_user_profile), methods=['PUT'])
account_bp.add_url_rule('/update-password', view_func=requires_module(SELF_SERVICE)(account_route.update_password), methods=['POST'])
account_bp.add_url_rule('/delete', view_func=requires_module(SELF_SERVICE)(account_route.delete_my_account), methods=['POST'])
