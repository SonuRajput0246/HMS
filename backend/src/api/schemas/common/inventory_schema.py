from decimal import Decimal
from src.api.schemas.fields.name import name_field
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory
from marshmallow import fields, validate, validates_schema, ValidationError

GetCategoryByIdSchema = id_schema_factory("id","Category Id", min_value=1)
UpsertCategoryIdSchema = id_schema_factory("id","Category Id", min_value=0)

class UpsertInventoryCategorySchema(UpsertCategoryIdSchema):
    name = name_field("Category Name")
    description = text_field(min_len=0, max_len=255, regex=None, required=True, allow_none=False, label="Description")
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)


GetInventoryById = id_schema_factory("id", "Inventory Id")
UpsertInventoryIdSchema = id_schema_factory("id","Inventory Id", min_value=0)
CategoryIdSchema = id_schema_factory("category_id","Category Id", min_value=1)

class UpsertInventorySchema(UpsertInventoryIdSchema, CategoryIdSchema):
    name = name_field("Inventory Name")
    quantity = fields.Decimal(
        required=True,
        as_string=True,
        validate=validate.Range(
            min=Decimal("1"),
            error="Quantity must be greater than 0"
        ),
        error_messages={"required": "Quantity is required"}
    )
    unit = fields.String(
        required=True,
        validate=validate.OneOf(
            ["pcs", "kg", "gm", "ltr", "ml"],
            error="Invalid unit"
        ),
        error_messages={"required": "Unit is required"}
    )
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)

    ## Purchase cost per unit, and the price an item rings up at when it is
    ## sold without being a recipe.
    ##
    ## Both are declared CMS-facing on the model and both are read by services:
    ## Recipe.calculate_cost_from_ingredients() multiplies each ingredient
    ## quantity by unit_cost, and OrderService reads selling_price when an
    ## item_type='inventory' line is rung up directly. Neither was reachable
    ## through this API, so the figures could only be set by editing the
    ## database -- every recipe therefore costed from whatever the seeder left,
    ## and a directly-sold item priced at zero.
    ##
    ## Optional and nullable on purpose: stock nobody has priced yet still has
    ## no cost, and null is how the cost model says "unknown" (it reads
    ## `unit_cost or 0`) rather than "free".
    unit_cost = fields.Decimal(
        required=False,
        allow_none=True,
        as_string=True,
        validate=validate.Range(
            min=Decimal("0"),
            error="Unit cost cannot be negative"
        ),
        error_messages={"invalid": "Unit cost must be a number"},
    )
    selling_price = fields.Decimal(
        required=False,
        allow_none=True,
        as_string=True,
        validate=validate.Range(
            min=Decimal("0"),
            error="Selling price cannot be negative"
        ),
        error_messages={"invalid": "Selling price must be a number"},
    )


@validates_schema
def validate_quantity_based_on_unit(self, data, **kwargs):
    quantity = data.get("quantity")
    unit = data.get("unit")

    if quantity is None or unit is None:
        return

    # If unit is pcs → quantity must be a whole number
    if unit == "pcs":
        if quantity != quantity.to_integral_value():
            raise ValidationError(
                "Quantity must be a whole number when unit is 'pcs'",
                field_name="quantity"
            )
