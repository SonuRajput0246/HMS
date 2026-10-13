from src.api.schemas.base import BaseSchema
from src.api.schemas.mixins.date_mixin import DateRangeValidationMixin
from src.api.schemas.fields.date import OptionalDateTimeField


class DateRangeSchema(BaseSchema, DateRangeValidationMixin):
    """
    Generic reusable date range schema.
    Child schemas only set field names.
    """
    allow_past_start_date = False

    start_date = OptionalDateTimeField
    end_date = OptionalDateTimeField
