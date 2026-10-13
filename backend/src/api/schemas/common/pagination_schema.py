from marshmallow import fields, validate
from src.api.schemas.common.base import BaseSchema


class PaginationSchema(BaseSchema):
    page_size = fields.Integer(
        required=True,
        allow_none=False,
        validate=validate.Range(min=1, error="Page size must be greater than 0"),
        error_messages={
            "required": "Page size is required",
            "null": "page_size cannot be null.",
            "invalid": "page_size must be an integer.",
        }
    )
    page_number = fields.Integer(
        required=True,
        allow_none=False,
        validate=validate.Range(min=1, error="Page number must be greater than 0"),
        error_messages={
            "required": "Page number is required",
            "null": "page_number cannot be null.",
            "invalid": "page_number must be an integer.",
        }
    )
    search_value = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(min=0)
    )
