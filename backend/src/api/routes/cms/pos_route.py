from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.pos_schema import GetBillSchema, GetPosSummarySchema
from src.api.services.cms.pos_service import PosService
from src.database.session import db_session


pos_bp = Blueprint("pos", __name__)


class PosRoute:
    def __init__(self, pos_service):
        self.pos_service = pos_service

    def get_bill(self):
        payload = request.get_json() or {}
        validated_data = GetBillSchema().load(payload)
        result, status_code = self.pos_service.get_bill(validated_data)
        return jsonify(result), status_code

    def get_summary(self):
        payload = request.get_json() or {}
        validated_data = GetPosSummarySchema().load(payload)
        result, status_code = self.pos_service.get_summary(validated_data)
        return jsonify(result), status_code


pos_service_instance = PosService(db=db_session)
pos_route = PosRoute(pos_service=pos_service_instance)


pos_bp.add_url_rule('/get-bill', view_func=requires_module("POS")(pos_route.get_bill), methods=['POST'])
pos_bp.add_url_rule('/get-summary', view_func=requires_module("POS")(pos_route.get_summary), methods=['POST'])