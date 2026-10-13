from marshmallow import fields, validate, ValidationError, validates_schema

from src.api.schemas.common.base import BaseSchema
from src.api.utils.datetime_helper import REPORT_PRESETS


## Report ranges are half-open in UTC [start, end). The upper bound is never
## compared with <=, so an order landing exactly on midnight is counted once,
## in one bucket, not twice across two days.
class BaseReportSchema(BaseSchema):
    """Common date-range plumbing for every report.

    `range` picks a preset; `custom` additionally needs from_date/to_date. The
    service resolves the preset into UTC bounds and echoes back the trading
    dates it actually covered, so the UI never has to re-derive the calendar.
    """

    range = fields.String(
        required=False, allow_none=False,
        load_default="today",
        validate=validate.OneOf(REPORT_PRESETS, error="Invalid report range"),
        error_messages={"invalid": "Invalid report range"}
    )
    from_date = fields.Date(required=False, allow_none=True)
    to_date = fields.Date(required=False, allow_none=True)

    @validates_schema
    def validate_custom_range(self, data, **kwargs):
        if data.get("range") == "custom":
            if not data.get("from_date") or not data.get("to_date"):
                raise ValidationError(
                    "from_date and to_date are required for a custom range.",
                    field_name="from_date"
                )
            if data["to_date"] < data["from_date"]:
                raise ValidationError(
                    "to_date cannot be earlier than from_date.",
                    field_name="to_date"
                )
        elif data.get("from_date") and not data.get("to_date"):
            ## A lone from_date with a preset is ambiguous: does the caller want
            ## an open-ended range, or did they mean custom?
            raise ValidationError(
                "Provide both from_date and to_date, or set range='custom'.",
                field_name="to_date"
            )


class SalesSummaryReportSchema(BaseReportSchema):
    include_hourly = fields.Boolean(required=False, allow_none=False, load_default=True)
    include_payment_breakdown = fields.Boolean(required=False, allow_none=False, load_default=True)


class ItemSalesReportSchema(BaseReportSchema):
    """Top sellers.

    sort_by drives whether "top" means volume or value -- a cafe's bestseller
    by quantity is often not its bestseller by margin, and both answers are
    wanted.
    """
    sort_by = fields.String(
        required=False, allow_none=False,
        load_default="quantity",
        validate=validate.OneOf(["quantity", "revenue"], error="Sort by quantity or revenue"),
        error_messages={"invalid": "Invalid sort_by value"}
    )
    limit = fields.Integer(
        required=False, allow_none=False,
        load_default=20,
        validate=validate.Range(min=1, max=200, error="Limit must be between 1 and 200"),
        error_messages={"invalid": "Limit must be an integer"}
    )
    ## Include recipes that sold nothing, so the operator can see what to cut.
    include_dead_stock = fields.Boolean(required=False, allow_none=False, load_default=False)
    station = fields.String(required=False, allow_none=True)


class DailyTrendReportSchema(BaseReportSchema):
    ## Zero-fill missing days in the response. Without this a chart shows a
    ## straight line across a closed Monday, reading as "steady trade".
    include_zero_days = fields.Boolean(required=False, allow_none=False, load_default=True)


class VoidReportSchema(BaseReportSchema):
    ## Loss prevention: who removed what, and what it was worth.
    group_by_staff = fields.Boolean(required=False, allow_none=False, load_default=True)
    limit = fields.Integer(
        required=False, allow_none=False,
        load_default=100,
        validate=validate.Range(min=1, max=500, error="Limit must be between 1 and 500"),
        error_messages={"invalid": "Limit must be an integer"}
    )


class KitchenReportSchema(BaseReportSchema):
    include_by_item = fields.Boolean(required=False, allow_none=False, load_default=True)
    ## Only lines the kitchen actually finished. Unstarted/timed-out lines are
    ## excluded rather than counted as zero, which would drag the average down
    ## and make a fast kitchen look slow.
    include_pending = fields.Boolean(required=False, allow_none=False, load_default=False)


class CustomerReportSchema(BaseReportSchema):
    limit = fields.Integer(
        required=False, allow_none=False,
        load_default=20,
        validate=validate.Range(min=1, max=200, error="Limit must be between 1 and 200"),
        error_messages={"invalid": "Limit must be an integer"}
    )