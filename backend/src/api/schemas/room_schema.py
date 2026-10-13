from marshmallow import fields, validate
from src.api.schemas.base import BaseSchema
from src.api.schemas.date_range_schema import DateRangeValidationMixin
from src.api.schemas.id_schema import id_schema_factory
from src.api.schemas.pagination_schema import PaginationSchema


RoomTypeIdSchema = id_schema_factory("room_type_id","Room Type Id", min_value=0, required=False)

class GetAllRoomsSchema(RoomTypeIdSchema, PaginationSchema):
    pass

GetRoomByIdSchema = id_schema_factory("id", "Room Id")

UpsertRoomIdSchema = id_schema_factory("id","Room Id", min_value=0)
UpsertRoomTypeIdSchema = id_schema_factory("room_type_id","Room Type Id", min_value=1, required=True)
UpsertFloorNumberSchema = id_schema_factory("floor_number","Floor Number")

class UpsertRoomSchema(UpsertRoomIdSchema, UpsertRoomTypeIdSchema, UpsertFloorNumberSchema):
    room_number = fields.String(
        required=True,
        allow_none=False,
        validate=[
            validate.Length(
                min=1,
                max=50,
                error="Room number must be between 1 to 50 characters or less"
            ),
            validate.Regexp(
                regex= r"^[A-Za-z0-9 '-]+$",
                error=f"Room number must contain only letters"
            )
        ],
        error_messages = {
            "required": "Room number is required",
            "null": "Room number cannot be null"
        }
    )
    room_status = fields.String(
        required=True,
        allow_none=False,
        validate=validate.OneOf(
            ["available", "reserved", "occupied", "cleaning", "maintenance", "out_of_service"],
            error="Invalid Room Status"
        )
    )
    reservation_status = fields.String(
        required=False,
        allow_none=True,
        validate = validate.OneOf(
            ["", "reserved", "checked_in", "checked_out", "cancelled"],
            error="Invalid Reservation Status"
        )
    )
    view = fields.String(
        required=False,
        allow_none=True,
        validate=[
            validate.Length(
                min=0,
                max=50,
                error="View must be between 1 to 50 characters or less"
            ),
            validate.Regexp(
                regex= r"^[A-Za-z0-9 '-]+$",
                error=f"View must contain only letters"
            )
        ]
    )
    notes = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(
            max=255,
            error="Notes must be 255 characters or less"
        )
    )
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)
