import logging

from flask import Blueprint, request, jsonify, make_response, current_app

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.common.auth_schema import RegisterUserSchema, VerifyEmailSchema, LoginSchema, SendOtpOnEmailSchema, \
    ActivateAccountSchema, ResetPasswordSchema
from src.api.services.common.auth_service import AuthService
from src.api.utils.jwt_helper import get_user_id_from_jwt
from src.database.session import db_session

auth_bp = Blueprint('auth', __name__)


class AuthRoute:
    def __init__(self, auth_service):
        self.auth_service = auth_service

    def _error_response(self, result):
        payload = {k: v for k, v in result.items() if k != "code"}
        return jsonify(payload), result["code"]

    def _success_response(self, result):
        return jsonify({
            "status": True,
            "message": result["message"],
            "data": result.get("data")
        }), result["code"]

    def _create_session_response(self, user, message):
        session_data = self.auth_service.generate_user_session(user)
        self.auth_service.db.commit()
        response = make_response(jsonify({
            "status": True,
            "message": message,
            "data": session_data["user_data"]
        }), 200)
        response.set_cookie(
            key="hms_refreshToken",
            value=session_data["refresh_token"],
            httponly=True,
            secure=current_app.config["COOKIE_SECURE"],
            samesite=current_app.config["COOKIE_SAMESITE"],
            max_age=60 * 60 * 24 * current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"],
            path="/"
        )
        return response

    def register(self):
        payload = request.get_json() or {}
        validated_data = RegisterUserSchema().load(payload)
        result, status_code = self.auth_service.register_user(validated_data)
        return jsonify(result), status_code

    def verify_email(self):
        payload = request.get_json() or {}
        validated_data = VerifyEmailSchema().load(payload)
        try:
            result = self.auth_service.verify_email(validated_data)
            if not result["status"]:
                return self._error_response(result)

            return self._create_session_response(result["data"], result["message"])
        except Exception as e:
            self.auth_service.db.rollback()
            logging.error(f"Verify Email Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500


    def initiate_setup_mfa(self, user_id):
        result, status_code = self.auth_service.initiate_setup_mfa(user_id)
        return jsonify(result), status_code


    def verify_and_enable_mfa(self):
        payload = request.get_json() or {}
        result, status_code = self.auth_service.verify_and_enable_mfa(payload)
        return jsonify(result), status_code


    def disable_mfa(self, user_id):
        result, status_code = self.auth_service.disable_mfa(user_id)
        return jsonify(result), status_code


    def login(self):
        payload = request.get_json() or {}
        validated_data = LoginSchema().load(payload)
        try:
            result = self.auth_service.user_login(validated_data)
            if not result["status"]:
                return self._error_response(result)

            if not result["is_session_req"]:
                return self._success_response(result)

            return self._create_session_response(result["data"], result["message"])
        except Exception as e:
            self.auth_service.db.rollback()
            logging.error(f"Login Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500


    def verify_mfa_login(self):
        payload = request.get_json() or {}
        try:
            result = self.auth_service.verify_mfa_login(payload)
            if not result["status"]:
                return self._error_response(result)

            return self._create_session_response(result["data"], result["message"])
        except Exception as e:
            self.auth_service.db.rollback()
            logging.error(f"Login Error: {str(e)}", exc_info=True)
            return jsonify(
                {"status": False, "message": "An internal server error occurred. Please try again later."}), 500


    def send_otp_on_email(self):
        payload = request.get_json() or {}
        validated_data = SendOtpOnEmailSchema().load(payload)
        result, status_code = self.auth_service.send_otp_on_email(validated_data)
        return jsonify(result), status_code


    def activate_account(self):
        payload = request.get_json() or {}
        validated_data = ActivateAccountSchema().load(payload)
        try:
            result = self.auth_service.activate_account(validated_data)
            if "error" in result:
                return jsonify({"status": False, "message": result["error"]}), result["code"]

            user = result["user"]
            session_data = self.auth_service.generate_user_session(user)
            self.auth_service.db.commit()
            response = make_response(jsonify({
                "status": True,
                "message": "Email activated successfully.",
                "data": session_data["user_data"]
            }), 200)

            response.set_cookie(
                key="hms_refreshToken",
                value=session_data["refresh_token"],
                httponly=True,
                secure=current_app.config["COOKIE_SECURE"],
                samesite=current_app.config["COOKIE_SAMESITE"],
                max_age=60 * 60 * 24 * current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"],
                path="/"
            )
            return response

        except Exception as e:
            self.auth_service.db.rollback()
            logging.error(f"Login Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500


    def get_fresh_tokens(self):
        try:
            result = self.auth_service.get_fresh_tokens()
            if "error" in result:
                return jsonify({"status": False, "message": result["error"]}), result["code"]

            user = result["user"]
            session_data = self.auth_service.generate_user_session(user)
            self.auth_service.db.commit()
            response = make_response(jsonify({
                "status": True,
                "message": "Fetched access token successfully.",
                "data": session_data["user_data"]
            }), 200)

            response.set_cookie(
                key="hms_refreshToken",
                value=session_data["refresh_token"],
                httponly=True,
                secure=current_app.config["COOKIE_SECURE"],
                samesite=current_app.config["COOKIE_SAMESITE"],
                max_age=60 * 60 * 24 * current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"],
                path="/"
            )
            return response

        except Exception as e:
            self.auth_service.db.rollback()
            logging.error(f"Login Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500

    def reset_password(self):
            payload = request.get_json() or {}
            validated_data = ResetPasswordSchema().load(payload)
            result, status_code = self.auth_service.reset_user_password(validated_data)
            return jsonify(result), status_code

    def logout(self):
        try:
            user_id = get_user_id_from_jwt()
            result = self.auth_service.logout_user(user_id)
            if "error" in result:
                return jsonify({"status": False, "message": result["error"]}), result["code"]

            response = make_response(
                jsonify({"status": True, "message": "Logged out successfully"}),
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
            self.auth_service.db.rollback()
            logging.error(f"Login Error: {str(e)}", exc_info=True)
            return jsonify({"status": False, "message": "An internal server error occurred. Please try again later."}), 500


## Instantiate service & Pass instance into route class
auth_service_instance = AuthService(db=db_session)
auth_route = AuthRoute(auth_service=auth_service_instance)

## Map multiple routes to the same instance
auth_bp.add_url_rule('/register', view_func=auth_route.register, methods=['POST'])
auth_bp.add_url_rule('/verify-email', view_func=auth_route.verify_email, methods=['POST'])
auth_bp.add_url_rule('/login', view_func=auth_route.login, methods=['POST'])
auth_bp.add_url_rule('/login/verify-totp', view_func=auth_route.verify_mfa_login, methods=['POST'])
auth_bp.add_url_rule('/send-otp', view_func=auth_route.send_otp_on_email, methods=['POST'])
auth_bp.add_url_rule('/activate-account', view_func=auth_route.activate_account, methods=['POST'])
auth_bp.add_url_rule('/get-fresh-token', view_func=auth_route.get_fresh_tokens, methods=['POST'])
auth_bp.add_url_rule('/reset-password', view_func=auth_route.reset_password, methods=['POST'])
auth_bp.add_url_rule('/logout', view_func=requires_module(SELF_SERVICE)(auth_route.logout), methods=['POST'])

auth_bp.add_url_rule('/setup-mfa/<int:user_id>', view_func=requires_module(SELF_SERVICE)(auth_route.initiate_setup_mfa), methods=['GET'])
auth_bp.add_url_rule('/setup-mfa/verify-totp', view_func=requires_module(SELF_SERVICE)(auth_route.verify_and_enable_mfa), methods=['POST'])
auth_bp.add_url_rule('/disable-mfa/<int:user_id>', view_func=requires_module(SELF_SERVICE)(auth_route.disable_mfa), methods=['GET'])


