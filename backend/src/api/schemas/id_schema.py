from marshmallow import fields, validate
from src.api.schemas.base import BaseSchema


def id_schema_factory(
    field_name: str,
    label: str = "Id",
    min_value: int = 1,
    required: bool = True
):
    """Build a single-field schema that validates an id.

    Every `*_by_id` endpoint in the API takes one identifier and nothing else,
    so this produces the schema rather than each endpoint declaring its own
    near-identical class.

    `min_value` exists because id 0 is not a row: a request for id 0 is a bug
    in the caller, and the alternative -- a 404 from the database -- reads like
    "that record does not exist" rather than "you sent nonsense".
    """
    return type(
        f"{label.replace(' ', '')}Schema",
        (BaseSchema,),
        {
            field_name: fields.Int(
                required=required,
                allow_none=False,
                validate=validate.Range(
                    min=min_value,
                    error=f"{label} must be greater than or equal to {min_value}"
                ),
                error_messages={
                    "required": f"{label} is required.",
                    "null": f"{label} cannot be null.",
                    "invalid": f"Invalid {label}."
                },
            )
        },
    )