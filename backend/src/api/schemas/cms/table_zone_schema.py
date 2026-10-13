from marshmallow import fields, validate

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.fields.name import name_field
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory


GetTableZoneByIdSchema = id_schema_factory("id", "Table Zone Id")
UpsertTableZoneIdSchema = id_schema_factory("id", "Table Zone Id", min_value=0)


class UpsertTableZoneSchema(UpsertTableZoneIdSchema):
    """id == 0 means create, anything else means update.

    is_deleted is how this codebase does deletes (soft delete via a flag on
    the same upsert payload) -- there is no separate delete endpoint for
    reference data.
    """

    name = name_field("Zone Name")
    display_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=50, error="Display Name must be between 1 and 50 characters"),
        error_messages={"required": "Display Name is required", "null": "Display Name cannot be null"}
    )
    description = text_field(
        max_len=255, min_len=0, required=False, allow_none=True, label="Description"
    )
    display_order = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=0, error="Display Order must be zero or greater"),
        error_messages={"invalid": "Display Order must be an integer"}
    )
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)