from datetime import datetime

from src.database.session import db_session
from flask import request, jsonify, Blueprint, g
from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.services.reservation_service import ReservationService
from src.api.schemas.reservation_schema import GetAvailableRoomSchema, CreateReservationSchema, GetAllReservationsSchema

reservation_bp = Blueprint('reservation', __name__)

class ReservationRoute:
    def __init__(self, reservation_service):
        self.reservation_service = reservation_service

    def get_all_reservations(self):
        payload = request.get_json() or {}
        validated_data = GetAllReservationsSchema().load(payload)
        result, status_code = self.reservation_service.get_all_reservations(validated_data)
        return jsonify(result), status_code

    def get_available_rooms(self):
        payload = request.get_json() or {}
        validated_data = GetAvailableRoomSchema().load(payload)
        result, status_code = self.reservation_service.get_available_rooms(validated_data)
        return jsonify(result), status_code

    def create_reservation_upsert_guest(self):
        payload = request.get_json() or {}
        result, status_code = self.reservation_service.create_reservation_upsert_guest(payload)
        return jsonify(result), status_code

    def update_reservation(self):
        payload = request.get_json() or {}
        result, status_code = self.reservation_service.update_reservation(payload)
        return jsonify(result), status_code

    def update_guests(self):
        payload = request.get_json() or {}
        result, status_code = self.reservation_service.update_guests(payload)
        return jsonify(result), status_code


    def delete_reservation(self, reservation_id):
        result, status_code = self.reservation_service.delete_reservation(reservation_id)
        return jsonify(result), status_code

    def cancel_reservation(self, reservation_id):
        # `silent=True` so an empty body yields {} and the service can return a
        # proper 422 for the missing reason, instead of Flask's bare 400.
        payload = request.get_json(silent=True) or {}
        # the acting user comes from the auth context set by jwt_required --
        # the client cannot nominate who cancelled their own booking
        payload['cancelled_by'] = g.current_user.id
        result, status_code = self.reservation_service.cancel_reservation(reservation_id, payload)
        return jsonify(result), status_code

    def get_reservation_by_id(self, reservation_id):
        result, status_code = self.reservation_service.get_reservation_by_id(reservation_id)
        return jsonify(result), status_code

    def insert_reservation_payment(self):
        payload = request.get_json() or {}
        result, status_code = self.reservation_service.insert_reservation_payment(payload)
        return jsonify(result), status_code



reservation_service_instance = ReservationService(db=db_session)
reservation_route = ReservationRoute(reservation_service=reservation_service_instance)
reservation_bp.add_url_rule('/get', view_func=requires_module("RESERVATIONS")(reservation_route.get_all_reservations), methods=['POST'])
reservation_bp.add_url_rule('/get-available-rooms', view_func=requires_module("RESERVATIONS")(reservation_route.get_available_rooms), methods=['POST'])
reservation_bp.add_url_rule('/create-reservation-upsert-guest', view_func=requires_module("RESERVATIONS")(reservation_route.create_reservation_upsert_guest), methods=['POST'])
reservation_bp.add_url_rule('/update', view_func=requires_module("RESERVATIONS")(reservation_route.update_reservation), methods=['PUT'])
reservation_bp.add_url_rule('/update-guests', view_func=requires_module("RESERVATIONS")(reservation_route.update_guests), methods=['POST'])
reservation_bp.add_url_rule('/delete/<int:reservation_id>', view_func=requires_module("RESERVATIONS")(reservation_route.delete_reservation), methods=['DELETE'])
## POST rather than PATCH: cancellation is a state transition with its own
## body (the reason), not a field update.
reservation_bp.add_url_rule('/cancel/<int:reservation_id>', view_func=requires_module("RESERVATIONS")(reservation_route.cancel_reservation), methods=['POST'])
reservation_bp.add_url_rule('/get-by-id/<int:reservation_id>', view_func=requires_module("RESERVATIONS")(reservation_route.get_reservation_by_id), methods=['GET'])
reservation_bp.add_url_rule('/payment-details', view_func=requires_module("RESERVATIONS")(reservation_route.insert_reservation_payment), methods=['POST'])