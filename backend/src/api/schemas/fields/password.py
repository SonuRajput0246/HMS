from marshmallow import validate, fields

from src.api.schemas.fields.constants import PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH


def update_password_field(label: str = "Password", required: bool = True):
    return fields.String(
        required=required,
        allow_none=False,
        validate=validate.Length(
            min=PASSWORD_MIN_LENGTH,
            max=PASSWORD_MAX_LENGTH,
            error=f"{label} must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters long"
        ),
        error_messages={
            "required": f"{label} is required",
            "null": f"{label} cannot be null"
        }
    )

def verify_password_field(label: str = "Password", required: bool = True):
    return fields.String(
        required=required,
        allow_none=False,
        validate=validate.Length(
            min=1,
            error=f"{label} is required"
        ),
        error_messages={
            "required": f"{label} is required",
            "null": f"{label} cannot be null"
        }
    )