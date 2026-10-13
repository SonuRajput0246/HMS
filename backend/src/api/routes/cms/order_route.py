from flask import Blueprint, request, jsonify
from flask import g

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.order_schema import (
    AddOrderItemSchema,
    CancelOrderSchema,
    CloseOrderSchema,
    CreateOrderSchema,
    GetOrderByIdSchema,
    GetOrdersSchema,
    ProcessPaymentSchema,
    UpdateOrderItemQuantitySchema,
    UpdateOrderStatusSchema,
    VoidOrderItemSchema,
)
from src.api.services.cms.order_service import OrderService
from src.database.session import db_session


order_bp = Blueprint("order", __name__)


class OrderRoute:
    def __init__(self, order_service):
        self.order_service = order_service

    ## The acting user comes off g, set by jwt_required, so no endpoint has to
    ## accept a created_by from the request body -- a client could otherwise
    ## forge who rang up an order.
    @property
    def _user_id(self):
        return g.current_user.id

    def create_order(self):
        payload = request.get_json() or {}
        validated_data = CreateOrderSchema().load(payload)
        result, status_code = self.order_service.create_order(validated_data, self._user_id)
        return jsonify(result), status_code

    def add_item(self, order_id):
        payload = request.get_json() or {}
        validated_data = AddOrderItemSchema().load(payload)
        result, status_code = self.order_service.add_item(order_id, validated_data)
        return jsonify(result), status_code

    def update_item_quantity(self, order_id):
        payload = request.get_json() or {}
        validated_data = UpdateOrderItemQuantitySchema().load(payload)
        result, status_code = self.order_service.update_item_quantity(order_id, validated_data)
        return jsonify(result), status_code

    def void_item(self, order_id):
        payload = request.get_json() or {}
        validated_data = VoidOrderItemSchema().load(payload)
        result, status_code = self.order_service.void_item(
            order_id, validated_data, self._user_id
        )
        return jsonify(result), status_code

    def update_status(self, order_id):
        payload = request.get_json() or {}
        validated_data = UpdateOrderStatusSchema().load(payload)
        result, status_code = self.order_service.update_status(order_id, validated_data)
        return jsonify(result), status_code

    def cancel_order(self, order_id):
        payload = request.get_json() or {}
        validated_data = CancelOrderSchema().load(payload)
        result, status_code = self.order_service.cancel_order(
            order_id, validated_data, self._user_id
        )
        return jsonify(result), status_code

    def process_payment(self, order_id):
        payload = request.get_json() or {}
        validated_data = ProcessPaymentSchema().load(payload)
        result, status_code = self.order_service.process_payment(
            order_id, validated_data, self._user_id
        )
        return jsonify(result), status_code

    def close_order(self, order_id):
        payload = request.get_json() or {}
        validated_data = CloseOrderSchema().load(payload)
        result, status_code = self.order_service.close_order(
            order_id, validated_data, self._user_id
        )
        return jsonify(result), status_code

    def get_order(self, order_id):
        result, status_code = self.order_service.get_order(order_id)
        return jsonify(result), status_code

    def get_orders(self):
        payload = request.get_json() or {}
        validated_data = GetOrdersSchema().load(payload)
        result, status_code = self.order_service.get_orders(validated_data)
        return jsonify(result), status_code

    def get_table_active_order(self, table_id):
        result, status_code = self.order_service.get_table_active_order(table_id)
        return jsonify(result), status_code


order_service_instance = OrderService(db=db_session)
order_route = OrderRoute(order_service=order_service_instance)


order_bp.add_url_rule('/create', view_func=requires_module("ORDER")(order_route.create_order), methods=['POST'])
order_bp.add_url_rule('/get', view_func=requires_module("ORDER")(order_route.get_orders), methods=['POST'])
order_bp.add_url_rule('/get-by-id/<int:order_id>', view_func=requires_module("ORDER")(order_route.get_order), methods=['GET'])
order_bp.add_url_rule('/get-active-by-table/<int:table_id>', view_func=requires_module("ORDER")(order_route.get_table_active_order), methods=['GET'])

order_bp.add_url_rule('/<int:order_id>/items', view_func=requires_module("ORDER")(order_route.add_item), methods=['POST'])
order_bp.add_url_rule('/<int:order_id>/items/update-quantity', view_func=requires_module("ORDER")(order_route.update_item_quantity), methods=['POST'])
order_bp.add_url_rule('/<int:order_id>/items/void', view_func=requires_module("ORDER")(order_route.void_item), methods=['POST'])

order_bp.add_url_rule('/<int:order_id>/status', view_func=requires_module("ORDER")(order_route.update_status), methods=['POST'])
order_bp.add_url_rule('/<int:order_id>/cancel', view_func=requires_module("ORDER")(order_route.cancel_order), methods=['POST'])
order_bp.add_url_rule('/<int:order_id>/payment', view_func=requires_module("ORDER")(order_route.process_payment), methods=['POST'])
order_bp.add_url_rule('/<int:order_id>/close', view_func=requires_module("ORDER")(order_route.close_order), methods=['POST'])