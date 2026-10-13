from marshmallow import fields

CheckInDateField = fields.DateTime(
    required=True,
    error_messages={
        "required": "Check-in date is required.",
        "invalid": "Invalid check-in date format."
    }
)

CheckOutDateField = fields.DateTime(
    required=True,
    error_messages={
        "required": "Check-out date is required.",
        "invalid": "Invalid check-out date format."
    }
)

OptionalDateTimeField = fields.DateTime(
    required=False,
    allow_none=True,
    error_messages={
        "invalid": "Invalid date format."
    }
)
