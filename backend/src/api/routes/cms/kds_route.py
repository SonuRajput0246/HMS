from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.kds_schema import (
    BumpOrderSchema,
    GetKdsTicketsSchema,
    UpdatePrepStatusSchema,
)
from src.api.services.cms.kds_service import KdsService
from src.database.session import db_session


kds_bp = Blueprint("kds", __name__)


class KdsRoute:
    def __init__(self, kds_service):
        self.kds_service = kds_service

    def get_tickets(self):
        payload = request.get_json() or {}
        validated_data = GetKdsTicketsSchema().load(payload)
        result, status_code = self.kds_service.get_tickets(validated_data)
        return jsonify(result), status_code

    def get_ticket(self, order_id):
        result, status_code = self.kds_service.get_ticket(order_id)
        return jsonify(result), status_code

    def get_station_summary(self):
        result, status_code = self.kds_service.get_station_summary()
        return jsonify(result), status_code

    def update_prep_status(self, order_id):
        payload = request.get_json() or {}
        validated_data = UpdatePrepStatusSchema().load(payload)
        result, status_code = self.kds_service.update_prep_status(order_id, validated_data)
        return jsonify(result), status_code

    def bump_order(self):
        payload = request.get_json() or {}
        validated_data = BumpOrderSchema().load(payload)
        result, status_code = self.kds_service.bump_order(validated_data)
        return jsonify(result), status_code


kds_service_instance = KdsService(db=db_session)
kds_route = KdsRoute(kds_service=kds_service_instance)


kds_bp.add_url_rule('/get-tickets', view_func=requires_module("KDS")(kds_route.get_tickets), methods=['POST'])
kds_bp.add_url_rule('/get-ticket/<int:order_id>', view_func=requires_module("KDS")(kds_route.get_ticket), methods=['GET'])
kds_bp.add_url_rule('/get-station-summary', view_func=requires_module("KDS")(kds_route.get_station_summary), methods=['GET'])
kds_bp.add_url_rule('/<int:order_id>/prep-status', view_func=requires_module("KDS")(kds_route.update_prep_status), methods=['POST'])
kds_bp.add_url_rule('/bump', view_func=requires_module("KDS")(kds_route.bump_order), methods=['POST'])