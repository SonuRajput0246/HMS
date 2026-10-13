from marshmallow import fields, validate

from src.api.schemas.fields.constants import NAME_MIN_LENGTH, NAME_MAX_LENGTH, NAME_REGEX


def name_field(label: str, required: bool = True):
    return fields.String(
        required=required,
        validate=[
            validate.Length(
                min=NAME_MIN_LENGTH,
                max=NAME_MAX_LENGTH,
                error=f"{label} must be between {NAME_MIN_LENGTH} and {NAME_MAX_LENGTH} characters long"
            ),
            validate.Regexp(
                regex=NAME_REGEX,
                error=f"{label} must contain only letters"
            )
        ],
        error_messages={
            "required": f"{label} is required",
            "null": f"{label} cannot be null"
        }
    )