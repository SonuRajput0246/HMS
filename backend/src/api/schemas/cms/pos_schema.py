from marshmallow import fields, validate

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.common.id_schema import id_schema_factory


GetOrderByIdForBillSchema = id_schema_factory("order_id", "Order Id")


class GetBillSchema(BaseSchema):
    """Receipt / bill for the till.

    A GET because a bill is a read model -- rendering it must never be able to
    change money. Printing and emailing are separate, explicit actions.
    """
    order_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Order Id must be greater than 0"),
        error_messages={"required": "Order Id is required", "invalid": "Invalid Order Id"}
    )
    ## Human-readable voucher lines (GST breakup, service charge, rounding) are
    ## computed here rather than stored, because Indian tax rules split a
    ## taxable amount from a GST amount rather than restating the whole total.
    include_tax_breakup = fields.Boolean(
        required=False, allow_none=False, load_default=True
    )


class GetPosSummarySchema(BaseSchema):
    """Header counters for the POS landing screen."""
    include_today_revenue = fields.Boolean(
        required=False, allow_none=False, load_default=True
    )