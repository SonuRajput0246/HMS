from marshmallow import fields, validate

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory


GetRecipeCategoryByIdSchema = id_schema_factory("id", "Recipe Category Id")
UpsertRecipeCategoryIdSchema = id_schema_factory("id", "Recipe Category Id", min_value=0)


class UpsertRecipeCategorySchema(UpsertRecipeCategoryIdSchema):
    name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=50, error="Category Name must be between 1 and 50 characters"),
        error_messages={"required": "Category Name is required", "null": "Category Name cannot be null"}
    )
    display_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=50, error="Display Name must be between 1 and 50 characters"),
        error_messages={"required": "Display Name is required", "null": "Display Name cannot be null"}
    )
    description = text_field(
        max_len=1000, min_len=0, required=False, allow_none=True, label="Description"
    )
    display_order = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=0, error="Display Order must be zero or greater"),
        error_messages={"invalid": "Display Order must be an integer"}
    )
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)


class GetRecipeCategoriesSchema(BaseSchema):
    page_size = fields.Integer(
        required=False, allow_none=False, load_default=100,
        validate=validate.Range(min=1, max=500, error="Page size must be between 1 and 500"),
        error_messages={"invalid": "Page size must be an integer"}
    )
    page_number = fields.Integer(
        required=False, allow_none=False, load_default=1,
        validate=validate.Range(min=1, error="Page number must be greater than 0"),
        error_messages={"invalid": "Page number must be an integer"}
    )
    search_value = fields.String(required=False, allow_none=True, validate=validate.Length(min=0))