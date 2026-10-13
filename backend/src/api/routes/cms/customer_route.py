from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.customer_schema import (
    GetCustomerByIdSchema,
    GetCustomersSchema,
    LookupByPhoneSchema,
    QuickCustomerSchema,
    RedeemPointsSchema,
    UpsertCustomerSchema,
)
from src.api.services.cms.customer_service import CustomerService
from src.database.session import db_session


customer_bp = Blueprint("customer", __name__)


class CustomerRoute:
    def __init__(self, customer_service):
        self.customer_service = customer_service

    def get_customers(self):
        payload = request.get_json() or {}
        validated_data = GetCustomersSchema().load(payload)
        result, status_code = self.customer_service.get_customers(validated_data)
        return jsonify(result), status_code

    def get_customer_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetCustomerByIdSchema().load(payload)
        result, status_code = self.customer_service.get_customer_by_id(validated_data["id"])
        return jsonify(result), status_code

    def lookup_by_phone(self):
        payload = request.get_json() or {}
        validated_data = LookupByPhoneSchema().load(payload)
        result, status_code = self.customer_service.lookup_by_phone(validated_data["phone"])
        return jsonify(result), status_code

    def quick_create_customer(self):
        payload = request.get_json() or {}
        validated_data = QuickCustomerSchema().load(payload)
        result, status_code = self.customer_service.quick_create_customer(validated_data)
        return jsonify(result), status_code

    def upsert_customer(self):
        payload = request.get_json() or {}
        validated_data = UpsertCustomerSchema().load(payload)
        result, status_code = self.customer_service.upsert_customer(validated_data)
        return jsonify(result), status_code

    def redeem_points(self):
        payload = request.get_json() or {}
        validated_data = RedeemPointsSchema().load(payload)
        result, status_code = self.customer_service.redeem_points(validated_data)
        return jsonify(result), status_code


customer_service_instance = CustomerService(db=db_session)
customer_route = CustomerRoute(customer_service=customer_service_instance)


customer_bp.add_url_rule('/get', view_func=requires_module("CUSTOMER")(customer_route.get_customers), methods=['POST'])
customer_bp.add_url_rule('/get-by-id', view_func=requires_module("CUSTOMER")(customer_route.get_customer_by_id), methods=['GET'])
customer_bp.add_url_rule('/lookup-by-phone', view_func=requires_module("CUSTOMER")(customer_route.lookup_by_phone), methods=['POST'])
customer_bp.add_url_rule('/quick-create', view_func=requires_module("CUSTOMER")(customer_route.quick_create_customer), methods=['POST'])
customer_bp.add_url_rule('/upsert', view_func=requires_module("CUSTOMER")(customer_route.upsert_customer), methods=['POST'])
customer_bp.add_url_rule('/redeem-points', view_func=requires_module("CUSTOMER")(customer_route.redeem_points), methods=['POST'])