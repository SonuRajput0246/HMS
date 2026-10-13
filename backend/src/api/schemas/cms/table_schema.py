from marshmallow import fields, validate, ValidationError

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.fields.name import name_field
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory


GetTableByIdSchema = id_schema_factory("id", "Table Id")
UpsertTableIdSchema = id_schema_factory("id", "Table Id", min_value=0)

## Mirrors Table.status. Kept as a literal list rather than importing the
## model so the schema layer stays independent of SQLAlchemy.
TABLE_STATUSES = ["available", "occupied", "reserved", "cleaning", "maintenance"]

## status values staff may set by hand. 'occupied' is excluded because it is
## owned by the order lifecycle -- a table becomes occupied when an order is
## opened against it and returns to available when that order is paid/closed.
## Allowing it here would let a table be marked occupied with no order, and
## then the order flow would refuse to seat a guest at it.
TABLE_STATUS_SETTABLE = ["available", "reserved", "cleaning", "maintenance"]

TABLE_SHAPES = ["square", "round", "rectangle"]


class UpsertTableSchema(UpsertTableIdSchema):
    table_number = fields.String(
        required=True,
        validate=validate.Length(min=1, max=20, error="Table Number must be between 1 and 20 characters"),
        error_messages={"required": "Table Number is required", "null": "Table Number cannot be null"}
    )
    table_name = text_field(
        max_len=50, min_len=0, required=False, allow_none=True, label="Table Name"
    )
    capacity = fields.Integer(
        required=True,
        validate=validate.Range(min=1, max=50, error="Capacity must be between 1 and 50"),
        error_messages={"required": "Capacity is required", "invalid": "Capacity must be an integer"}
    )
    status = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(TABLE_STATUS_SETTABLE, error="Invalid table status"),
        error_messages={"invalid": "Invalid table status"}
    )
    zone_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Zone Id must be greater than 0"),
        error_messages={"invalid": "Zone Id must be an integer"}
    )
    position_x = fields.Integer(required=False, allow_none=True)
    position_y = fields.Integer(required=False, allow_none=True)
    shape = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(TABLE_SHAPES, error="Invalid table shape"),
        error_messages={"invalid": "Invalid table shape"}
    )
    is_combinable = fields.Boolean(required=False, allow_none=True)
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)


class UpsertTableStatusSchema(BaseSchema):
    """Manual status flip from the table management screen.

    Rejects 'occupied' for the same reason UpsertTableSchema does: occupancy is
    owned by the order lifecycle.
    """
    id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Table Id must be greater than 0"),
        error_messages={"required": "Table Id is required", "invalid": "Invalid Table Id"}
    )
    status = fields.String(
        required=True,
        validate=validate.OneOf(TABLE_STATUS_SETTABLE, error="Invalid table status"),
        error_messages={"required": "Status is required", "invalid": "Invalid table status"}
    )
    remarks = text_field(max_len=255, min_len=0, required=False, allow_none=True, label="Remarks")


class GetTablesSchema(BaseSchema):
    """Paginated table list with optional filters.

    Default page_size is generous because the table floor grid is usually
    loaded in one shot rather than page by page.
    """
    page_size = fields.Integer(
        required=False, allow_none=False,
        load_default=100,
        validate=validate.Range(min=1, max=500, error="Page size must be between 1 and 500"),
        error_messages={"invalid": "Page size must be an integer"}
    )
    page_number = fields.Integer(
        required=False, allow_none=False,
        load_default=1,
        validate=validate.Range(min=1, error="Page number must be greater than 0"),
        error_messages={"invalid": "Page number must be an integer"}
    )
    zone_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Zone Id must be greater than 0"),
        error_messages={"invalid": "Zone Id must be an integer"}
    )
    status = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(TABLE_STATUSES, error="Invalid table status"),
        error_messages={"invalid": "Invalid table status"}
    )
    search_value = fields.String(required=False, allow_none=True, validate=validate.Length(min=0))