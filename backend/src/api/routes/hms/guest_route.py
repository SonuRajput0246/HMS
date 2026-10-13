from flask import request, jsonify, Blueprint

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.hms.guest_schema import GetAllGuestsSchema, GetGuestByIdSchema
from src.api.services.hms.guest_service import GuestService
from src.database.session import db_session

guest_bp = Blueprint('guest', __name__)

class GuestRoute:
    def __init__(self, guest_service):
        self.guest_service = guest_service

    def get_all_guests(self):
        payload = request.get_json() or {}
        validated_data = GetAllGuestsSchema().load(payload)
        result, status_code = self.guest_service.get_all_guests(validated_data)
        return jsonify(result), status_code

    def get_guest_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetGuestByIdSchema().load(payload)
        result, status_code = self.guest_service.get_guest_by_id(validated_data['id'])
        return jsonify(result), status_code

    def upsert_guest(self):
        payload = request.get_json() or {}
        result, status_code = self.guest_service.upsert_guest(payload)
        return jsonify(result), status_code


guest_service_instance = GuestService(db=db_session)
guest_route = GuestRoute(guest_service=guest_service_instance)
guest_bp.add_url_rule('/get-all', view_func=requires_module("GUEST")(guest_route.get_all_guests), methods=['POST'])
guest_bp.add_url_rule('/get-by-id', view_func=requires_module("GUEST")(guest_route.get_guest_by_id), methods=['GET'])
guest_bp.add_url_rule('/upsert', view_func=requires_module("GUEST")(guest_route.upsert_guest), methods=['POST'])
