from decimal import Decimal
from marshmallow import fields, validate, ValidationError, validates_schema

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory


GetRecipeByIdSchema = id_schema_factory("id", "Recipe Id")
UpsertRecipeIdSchema = id_schema_factory("id", "Recipe Id", min_value=0)


class UpsertRecipeSchema(UpsertRecipeIdSchema):
    """Create or update a menu item.

    `station` is validated against the 'recipe_station' enum definition in the
    service layer (EnumHelper), not here: marshmallow schemas are static and
    cannot read the enum tables, so a literal list would become a second source
    of truth that drifts the moment an admin adds a station.

    cost_price is deliberately NOT accepted. It is derived from the linked
    recipe_ingredients by Recipe.update_cost_price() whenever an ingredient
    changes, so accepting it from a client would let the recipe screen show a
    margin that the ingredient editor immediately contradicts.
    """

    name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100, error="Recipe Name must be between 1 and 100 characters"),
        error_messages={"required": "Recipe Name is required", "null": "Recipe Name cannot be null"}
    )
    display_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100, error="Display Name must be between 1 and 100 characters"),
        error_messages={"required": "Display Name is required", "null": "Display Name cannot be null"}
    )
    category_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Category Id must be greater than 0"),
        error_messages={"invalid": "Category Id must be an integer"}
    )
    description = text_field(
        max_len=1000, min_len=0, required=False, allow_none=True, label="Description"
    )
    instructions = text_field(
        max_len=2000, min_len=0, required=False, allow_none=True, label="Instructions"
    )
    image_url = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=500, error="Image URL is too long"),
        error_messages={"invalid": "Image URL is too long"}
    )
    selling_price = fields.Decimal(
        required=True, as_string=True,
        validate=validate.Range(min=Decimal("0"), error="Selling price cannot be negative"),
        error_messages={"required": "Selling price is required", "invalid": "Selling price must be a number"}
    )
    station = fields.String(
        required=False, allow_none=False,
        load_default="other",
        validate=validate.Length(min=1, max=20, error="Station must be between 1 and 20 characters"),
        error_messages={"invalid": "Station must be a valid kitchen station"}
    )
    prep_time_minutes = fields.Integer(
        required=False, allow_none=False, load_default=0,
        validate=validate.Range(min=0, max=1440, error="Prep time must be between 0 and 1440 minutes"),
        error_messages={"invalid": "Prep time must be an integer"}
    )
    cook_time_minutes = fields.Integer(
        required=False, allow_none=False, load_default=0,
        validate=validate.Range(min=0, max=1440, error="Cook time must be between 0 and 1440 minutes"),
        error_messages={"invalid": "Cook time must be an integer"}
    )
    is_vegetarian = fields.Boolean(required=False, allow_none=False, load_default=False)
    is_vegan = fields.Boolean(required=False, allow_none=False, load_default=False)
    is_spicy = fields.Boolean(required=False, allow_none=False, load_default=False)
    default_spice_level = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=20, error="Spice level is too long"),
        error_messages={"invalid": "Invalid spice level"}
    )
    is_recommended = fields.Boolean(required=False, allow_none=False, load_default=False)
    is_available = fields.Boolean(required=False, allow_none=False, load_default=True)
    display_order = fields.Integer(
        required=False, allow_none=False, load_default=0,
        validate=validate.Range(min=0, error="Display Order must be zero or greater"),
        error_messages={"invalid": "Display Order must be an integer"}
    )
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)

    @validates_schema
    def validate_diet_flags(self, data, **kwargs):
        ## Vegan is a subset of vegetarian. Rejecting the impossible pair here
        ## gives the operator a clear message instead of a contradictory menu
        ## badge that the customer can see.
        if data.get("is_vegan") and not data.get("is_vegetarian"):
            raise ValidationError(
                "A vegan recipe must also be marked vegetarian.",
                field_name="is_vegetarian"
            )


class UpdateRecipeAvailabilitySchema(BaseSchema):
    """Toggle sellable / 86'd without opening the full recipe form.

    is_available is separate from is_active on purpose: a dish that is out of
    stock for an afternoon is still an active part of the menu, it just cannot
    be rung up right now.
    """
    id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Recipe Id must be greater than 0"),
        error_messages={"required": "Recipe Id is required", "invalid": "Invalid Recipe Id"}
    )
    is_available = fields.Boolean(required=True)
    reason = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=255, error="Reason is too long"),
        error_messages={"invalid": "Reason is too long"}
    )


class GetRecipesSchema(BaseSchema):
    page_size = fields.Integer(
        required=False, allow_none=False, load_default=20,
        validate=validate.Range(min=1, max=200, error="Page size must be between 1 and 200"),
        error_messages={"invalid": "Page size must be an integer"}
    )
    page_number = fields.Integer(
        required=False, allow_none=False, load_default=1,
        validate=validate.Range(min=1, error="Page number must be greater than 0"),
        error_messages={"invalid": "Page number must be an integer"}
    )
    category_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Category Id must be greater than 0"),
        error_messages={"invalid": "Category Id must be an integer"}
    )
    station = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=20, error="Station is too long"),
        error_messages={"invalid": "Invalid station"}
    )
    is_available = fields.Boolean(required=False, allow_none=True)
    is_vegetarian = fields.Boolean(required=False, allow_none=True)
    is_recommended = fields.Boolean(required=False, allow_none=True)
    search_value = fields.String(required=False, allow_none=True, validate=validate.Length(min=0))


class GetMenuSchema(BaseSchema):
    """Full menu for the POS / KDS picker.

    Defaults to sellable-only and live stock, which is what the till wants.
    include_unavailable exists so a manager can preview the whole menu and
    spot what is 86'd.
    """
    category_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Category Id must be greater than 0"),
        error_messages={"invalid": "Category Id must be an integer"}
    )
    station = fields.String(required=False, allow_none=True)
    include_unavailable = fields.Boolean(required=False, allow_none=False, load_default=False)