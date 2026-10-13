from marshmallow import fields, validate

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.common.id_schema import id_schema_factory
from src.api.models.cms.order_model import PREP_STATUS_SETTABLE


GetOrderByIdForKdsSchema = id_schema_factory("order_id", "Order Id")
GetOrderItemByIdForKdsSchema = id_schema_factory("order_item_id", "Order Item Id")


class GetKdsTicketsSchema(BaseSchema):
    """The kitchen queue.

    Defaults to every station so an unconfigured screen still shows work rather
    than an empty board; pass station to run one screen per pass.
    """
    station = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=30, error="Station is too long"),
        error_messages={"invalid": "Invalid station"}
    )
    ## Newest ticket last by default, which is the order work should be done in.
    order_by = fields.String(
        required=False, allow_none=False,
        load_default="oldest_first",
        validate=validate.OneOf(
            ["oldest_first", "newest_first"],
            error="Order by must be oldest_first or newest_first"
        ),
        error_messages={"invalid": "Invalid order_by value"}
    )
    ## Overdue-first is the cook's real need: sort by how long it has been
    ## waiting rather than by id.
    include_ready = fields.Boolean(
        required=False, allow_none=False, load_default=False
    )


class UpdatePrepStatusSchema(BaseSchema):
    """Move one line through the kitchen.

    The item id is the body payload and the order comes from the path; the
    service re-checks that the item really belongs to that order so a mismatched
    pair cannot advance an unrelated line.
    """
    order_item_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Order Item Id must be greater than 0"),
        error_messages={"required": "Order Item Id is required", "invalid": "Invalid Order Item Id"}
    )
    prep_status = fields.String(
        required=True,
        validate=validate.OneOf(PREP_STATUS_SETTABLE, error="Invalid prep status"),
        error_messages={"required": "Prep status is required", "invalid": "Invalid prep status"}
    )


class BumpOrderSchema(BaseSchema):
    """Mark every still-cooking line on one ticket as ready.

    Used by the KDS "bump" button when a whole table goes out together.
    """
    order_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Order Id must be greater than 0"),
        error_messages={"required": "Order Id is required", "invalid": "Invalid Order Id"}
    )
    station = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=30, error="Station is too long"),
        error_messages={"invalid": "Invalid station"}
    )