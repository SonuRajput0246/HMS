from marshmallow import fields, validate


def email_field(required: bool = True, allow_none: bool = False):
    return fields.Email(
        required=required,
        allow_none=allow_none,
        validate=[validate.Length(max=255, error="Email must be less than 255 characters")],
        error_messages={
            "required": "Email is required",
            "null": "Email cannot be null",
            "invalid": "Invalid email address"
        }
    )