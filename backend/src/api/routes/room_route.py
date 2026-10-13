from src.database.session import db_session
from flask import request, jsonify, Blueprint
from src.api.services.room_service import RoomService
from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.room_schema import GetAllRoomsSchema, GetRoomByIdSchema, UpsertRoomSchema

room_bp = Blueprint('room', __name__)

class RoomRoute:
    def __init__(self, room_service):
        self.room_service = room_service

    def get_room_types(self):
        result, status_code = self.room_service.get_room_types()
        return jsonify(result), status_code

    def get_all_rooms(self):
        payload = request.get_json() or {}
        validated_data = GetAllRoomsSchema().load(payload)
        result, status_code = self.room_service.get_all_rooms(validated_data)
        return jsonify(result), status_code

    def get_room_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetRoomByIdSchema().load(payload)
        result, status_code = self.room_service.get_room_by_id(validated_data['id'])
        return jsonify(result), status_code

    def upsert_room(self):
        payload = request.get_json() or {}
        validated_data = UpsertRoomSchema().load(payload)
        result, status_code = self.room_service.upsert_room(validated_data)
        return jsonify(result), status_code


room_service_instance = RoomService(db=db_session)
room_route = RoomRoute(room_service=room_service_instance)
room_bp.add_url_rule('/get-types', view_func=requires_module("ROOM")(room_route.get_room_types), methods=['GET'])
room_bp.add_url_rule('/get-all', view_func=requires_module("ROOM")(room_route.get_all_rooms), methods=['POST'])
room_bp.add_url_rule('/get-by-id', view_func=requires_module("ROOM")(room_route.get_room_by_id), methods=['GET'])
room_bp.add_url_rule('/upsert', view_func=requires_module("ROOM")(room_route.upsert_room), methods=['POST'])

