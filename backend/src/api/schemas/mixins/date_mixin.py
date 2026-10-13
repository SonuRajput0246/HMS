from datetime import datetime
from marshmallow import validates_schema, ValidationError


class DateRangeValidationMixin:
    """
    Generic date range validation mixin.
    Can be reused with any date field names.
    """

    ## Default field names (can be overridden in schema)
    start_date_field = None
    end_date_field = None

    ## Control whether past dates are allowed
    allow_past_start_date = False

    @validates_schema
    def validate_date_range(self, data, **kwargs):
        if not self.start_date_field or not self.end_date_field:
            return

        start_date = data.get(self.start_date_field)
        end_date = data.get(self.end_date_field)

        today = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        ## Start date must not be in the past
        if (
            not self.allow_past_start_date
            and start_date
            and start_date < today
        ):
            raise ValidationError(
                f"{self.start_date_field.replace('_', ' ').title()} cannot be in the past.",
                field_name=self.start_date_field
            )

        ## End date must be after start date
        if start_date and end_date and end_date < start_date:
            raise ValidationError(
                f"{self.end_date_field.replace('_', ' ').title()} must be after "
                f"{self.start_date_field.replace('_', ' ').title()}.",
                field_name=self.end_date_field
            )














