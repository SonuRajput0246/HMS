from decimal import Decimal
from marshmallow import fields, validate, ValidationError, validates_schema

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory


## Note: there is no "recipe_id" body schema here. The recipe always comes
## from the URL path, so a crafted payload cannot move an ingredient line to a
## different recipe. The nested replace schema is the one exception and it
## takes recipe_id in the body purely so its uniqueness check has a field to
## hang off; the route overwrites it with the path value before the service
## ever sees it.
UpsertRecipeIngredientIdSchema = id_schema_factory("id", "Recipe Ingredient Id", min_value=0)

## Units an ingredient line may use. Deliberately broader than the Inventory
## unit allow-list (pcs/kg/gm/ltr/ml): a recipe line is often a *portion* of a
## bulk stock unit, e.g. "60 ml" of oil per burger, so a plain ml value has to
## be expressible even when no such inventory row uses ml alone.
INGREDIENT_UNITS = ["pcs", "kg", "gm", "mg", "ltr", "ml"]


class UpsertRecipeIngredientSchema(UpsertRecipeIngredientIdSchema):
    """Add or edit one ingredient line on a recipe.

    The recipe comes from the URL path, not the body, so an ingredient row can
    never be reassigned to a different recipe by a crafted payload.
    """

    inventory_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Inventory Id must be greater than 0"),
        error_messages={"required": "Inventory Id is required", "invalid": "Inventory Id must be an integer"}
    )
    quantity = fields.Decimal(
        required=True, as_string=True,
        validate=validate.Range(min=Decimal("0.001"), error="Quantity must be greater than 0"),
        error_messages={"required": "Quantity is required", "invalid": "Quantity must be a number"}
    )
    unit = fields.String(
        required=True,
        validate=validate.OneOf(INGREDIENT_UNITS, error="Invalid unit"),
        error_messages={"required": "Unit is required", "invalid": "Invalid unit"}
    )
    is_optional = fields.Boolean(required=False, allow_none=False, load_default=False)
    is_prepped = fields.Boolean(required=False, allow_none=False, load_default=False)


class ReplaceRecipeIngredientsSchema(BaseSchema):
    """Replace the whole ingredient list in one call.

    The recipe editor holds a grid of rows, so save-the-whole-grid is the
    natural interaction; sending deltas would mean the client reconciling
    which rows were added, edited or removed. Rows are matched to existing
    lines by inventory_id, so a client that keeps the ids it was given updates
    in place and any inventory_id it omits is soft-deleted.
    """

    recipe_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Recipe Id must be greater than 0"),
        error_messages={"required": "Recipe Id is required", "invalid": "Invalid Recipe Id"}
    )
    ingredients = fields.List(
        fields.Nested(
            UpsertRecipeIngredientSchema,
            ## Nested schema carries its own id; inside a replace payload that
            ## id is only a hint for matching and 0 means "new row".
            many=True,
            only=("id", "inventory_id", "quantity", "unit", "is_optional", "is_prepped")
        ),
        required=True,
        validate=validate.Length(min=0, max=100, error="A recipe can have at most 100 ingredients")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @validates_schema
    def validate_unique_inventory(self, data, **kwargs):
        """One row per inventory item.

        The database has a matching unique constraint on
        (recipe_id, inventory_id), so without this the operator would only
        discover the problem as a raw IntegrityError surfacing as a 500.
        """
        seen = set()
        for idx, ing in enumerate(data.get("ingredients") or []):
            inv_id = ing.get("inventory_id")
            if inv_id in seen:
                raise ValidationError(
                    "Each inventory item can appear only once in a recipe.",
                    field_name=f"ingredients[{idx}].inventory_id"
                )
            seen.add(inv_id)