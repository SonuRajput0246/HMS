from src.api.schemas.common.date_range_schema import DateRangeSchema
from marshmallow import fields, validate

from src.api.schemas.common.id_schema import id_schema_factory
from src.api.schemas.common.pagination_schema import PaginationSchema
from src.api.schemas.fields.date import OptionalDateTimeField, CheckInDateField, CheckOutDateField

RoomTypeIdOptionalSchema = id_schema_factory("room_type_id", "Room Type Id", min_value=0, required=False)

class GetAvailableRoomSchema(DateRangeSchema, PaginationSchema, RoomTypeIdOptionalSchema):
    start_date_field = "check_in"       ## Tell mixin which field to use
    end_date_field = "check_out"        ## Tell mixin which field to use
    check_in = OptionalDateTimeField
    check_out = OptionalDateTimeField


RoomIdRequiredSchema = id_schema_factory("room_id","Room Id", min_value=1)

class CreateReservationSchema(RoomIdRequiredSchema):
    start_date_field = "check_in_date"      ## Tell mixin which field to use
    end_date_field = "check_out_date"       ## Tell mixin which field to use
    check_in_date = CheckInDateField
    check_out_date = CheckOutDateField


class GetAllReservationsSchema(DateRangeSchema, PaginationSchema):
    start_date_field = "from_date"      ## Tell mixin which field to use
    end_date_field = "to_date"          ## Tell mixin which field to use
    allow_past_start_date = True    ## reports usually allow past dates
    from_date = OptionalDateTimeField
    to_date = OptionalDateTimeField
    search_room_number_value = fields.String(required=False, allow_none=True)
    ## Allowed values are NOT listed here. They come from the `reservation_status`
    ## enum definition (enum_seeder.py) and are validated in
    ## reservation_service, so an admin adding a status does not also need a
    ## backend deploy.
    ##
    ## The list this replaced was ["", "reserved", "checked_in", "checked_out",
    ## "cancelled"] -- it omitted `created`, which is the state a new booking
    ## actually opens in, so filtering the grid by the default state returned
    ## nothing. Do not reintroduce a hardcoded list.
    reservation_status = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(min=0, max=30),
    )