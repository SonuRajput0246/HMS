from decimal import Decimal
from marshmallow import fields, validate, ValidationError, validates_schema

from src.api.schemas.common.base import BaseSchema
from src.api.schemas.fields.text import text_field
from src.api.schemas.common.id_schema import id_schema_factory
from src.api.models.cms.order_model import (
    OrderStatusEnum,
    OrderTypeEnum,
    PaymentMethodEnum,
)


GetOrderByIdSchema = id_schema_factory("id", "Order Id")
GetOrderItemByIdSchema = id_schema_factory("id", "Order Item Id")

## Enum members are read off the model so the schema can never drift out of
## sync with the database column.
ORDER_TYPES = [e.value for e in OrderTypeEnum]
ORDER_STATUSES = [e.value for e in OrderStatusEnum]
PAYMENT_STATUSES = ["pending", "partial", "paid", "refunded", "failed"]
PAYMENT_METHODS = [e.value for e in PaymentMethodEnum]

## What staff may set through the generic status endpoint. 'cancelled' is
## excluded because cancelling requires a reason, so it has its own action.
ORDER_STATUS_SETTABLE = ["confirmed", "preparing", "ready", "served"]

## Modifiers is a free-form JSON bag (extra cheese, less ice, etc). Validated
## as a dict so a list or scalar cannot slip through into the column.
MAX_MODIFIER_KEYS = 20


class CreateOrderSchema(BaseSchema):
    """Open an order against a table, a customer, or as a plain walk-in.

    reference_type/reference_id is the polymorphic anchor. table_id and
    customer_id are derived from it server-side rather than trusted from the
    client, so the two can never disagree.
    """

    reference_type = fields.String(
        required=True,
        validate=validate.OneOf(
            ["table", "customer", "walkin"],
            error="Reference type must be table, customer or walkin"
        ),
        error_messages={"required": "Reference type is required", "invalid": "Invalid reference type"}
    )
    reference_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=0, error="Reference Id must be zero or greater"),
        error_messages={"invalid": "Reference Id must be an integer"}
    )
    order_type = fields.String(
        required=False, allow_none=False,
        load_default=OrderTypeEnum.DINE_IN.value,
        validate=validate.OneOf(ORDER_TYPES, error="Invalid order type"),
        error_messages={"invalid": "Invalid order type"}
    )
    tax_amount = fields.Decimal(
        required=False, allow_none=True, as_string=True,
        validate=validate.Range(min=Decimal("0"), error="Tax amount cannot be negative"),
        error_messages={"invalid": "Tax amount must be a number"}
    )
    discount_amount = fields.Decimal(
        required=False, allow_none=True, as_string=True,
        validate=validate.Range(min=Decimal("0"), error="Discount cannot be negative"),
        error_messages={"invalid": "Discount amount must be a number"}
    )
    notes = text_field(max_len=500, min_len=0, required=False, allow_none=True, label="Notes")
    kitchen_notes = text_field(max_len=500, min_len=0, required=False, allow_none=True, label="Kitchen Notes")

    @validates_schema
    def validate_reference(self, data, **kwargs):
        ref_type = data.get("reference_type")
        ref_id = data.get("reference_id")

        if ref_type == "walkin":
            # A walk-in has no parent row. Force reference_id to 0 rather than
            # rejecting a stray id, so the caller gets a clean walk-in order.
            data["reference_id"] = 0
        elif ref_type in ("table", "customer"):
            if not ref_id:
                raise ValidationError(
                    f"reference_id is required when reference_type is '{ref_type}'",
                    field_name="reference_id"
                )


class AddOrderItemSchema(BaseSchema):
    """Add one line to an order.

    Exactly one of recipe_id / inventory_item_id must be present -- that is
    what decides item_type and which price column is read. unit_price is not
    accepted from the client for recipe items (the recipe owns its price); it
    IS accepted for inventory items, but only as an override when that item
    has no selling_price set.
    """

    recipe_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Recipe Id must be greater than 0"),
        error_messages={"invalid": "Recipe Id must be an integer"}
    )
    inventory_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Inventory Id must be greater than 0"),
        error_messages={"invalid": "Inventory Id must be an integer"}
    )
    quantity = fields.Decimal(
        required=True, as_string=True,
        validate=validate.Range(min=Decimal("0.001"), error="Quantity must be greater than 0"),
        error_messages={"required": "Quantity is required", "invalid": "Quantity must be a number"}
    )
    unit_price = fields.Decimal(
        required=False, allow_none=True, as_string=True,
        validate=validate.Range(min=Decimal("0"), error="Unit price cannot be negative"),
        error_messages={"invalid": "Unit price must be a number"}
    )
    modifiers = fields.Dict(required=False, allow_none=True)
    cooking_instructions = text_field(
        max_len=500, min_len=0, required=False, allow_none=True, label="Cooking Instructions"
    )
    spice_level = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(
            ["none", "mild", "medium", "hot", "extra_hot"],
            error="Invalid spice level"
        ),
        error_messages={"invalid": "Invalid spice level"}
    )

    @validates_schema
    def validate_exactly_one_item(self, data, **kwargs):
        recipe_id = data.get("recipe_id")
        inventory_id = data.get("inventory_id")

        if recipe_id and inventory_id:
            raise ValidationError(
                "Provide either recipe_id or inventory_id, not both",
                field_name="recipe_id"
            )
        if not recipe_id and not inventory_id:
            raise ValidationError(
                "Either recipe_id or inventory_id is required",
                field_name="recipe_id"
            )

        if data.get("modifiers") and len(data["modifiers"]) > MAX_MODIFIER_KEYS:
            raise ValidationError(
                f"At most {MAX_MODIFIER_KEYS} modifiers are allowed",
                field_name="modifiers"
            )


class UpdateOrderItemQuantitySchema(BaseSchema):
    order_item_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Order Item Id must be greater than 0"),
        error_messages={"required": "Order Item Id is required", "invalid": "Invalid Order Item Id"}
    )
    quantity = fields.Decimal(
        required=True, as_string=True,
        validate=validate.Range(min=Decimal("0.001"), error="Quantity must be greater than 0"),
        error_messages={"required": "Quantity is required", "invalid": "Quantity must be a number"}
    )


class VoidOrderItemSchema(BaseSchema):
    """Void a line.

    The order id is passed as a URL path param and the item id in the body,
    matching how the other upsert endpoints pair a primary key with a payload.
    reason is mandatory because a voided line is a money event that the owner
    will ask about later.
    """
    order_item_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1, error="Order Item Id must be greater than 0"),
        error_messages={"required": "Order Item Id is required", "invalid": "Invalid Order Item Id"}
    )
    reason = fields.String(
        required=True,
        validate=validate.Length(min=3, max=255, error="Reason must be between 3 and 255 characters"),
        error_messages={"required": "Reason is required", "null": "Reason cannot be null"}
    )


class ProcessPaymentSchema(BaseSchema):
    """Record one payment against an order.

    A split bill is simply several ProcessPayment calls sharing a
    split_group_id. There is no per-row split strategy -- the caller decides
    the amounts. split_payer_name is what the receipt shows for that share.
    """

    amount = fields.Decimal(
        required=True, as_string=True,
        validate=validate.Range(min=Decimal("0.01"), error="Amount must be greater than 0"),
        error_messages={"required": "Amount is required", "invalid": "Amount must be a number"}
    )
    payment_method = fields.String(
        required=True,
        validate=validate.OneOf(PAYMENT_METHODS, error="Invalid payment method"),
        error_messages={"required": "Payment method is required", "invalid": "Invalid payment method"}
    )
    transaction_ref = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=100, error="Transaction reference is too long"),
        error_messages={"invalid": "Transaction reference is too long"}
    )
    split_group_id = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=50, error="Split group id is too long"),
        error_messages={"invalid": "Split group id is too long"}
    )
    split_payer_name = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=100, error="Split payer name is too long"),
        error_messages={"invalid": "Split payer name is too long"}
    )
    remarks = text_field(max_len=255, min_len=0, required=False, allow_none=True, label="Remarks")


class CloseOrderSchema(BaseSchema):
    """Close a paid order.

    complete_payment lets the till take the balance and close in one call,
    which is the common case. Set false to close an order that was already
    settled in instalments.
    """
    complete_payment = fields.Boolean(
        required=False, allow_none=False, load_default=False
    )
    payment_method = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(PAYMENT_METHODS, error="Invalid payment method"),
        error_messages={"invalid": "Invalid payment method"}
    )
    transaction_ref = fields.String(required=False, allow_none=True)


class UpdateOrderStatusSchema(BaseSchema):
    status = fields.String(
        required=True,
        validate=validate.OneOf(ORDER_STATUS_SETTABLE, error="Invalid order status"),
        error_messages={"required": "Status is required", "invalid": "Invalid order status"}
    )


class CancelOrderSchema(BaseSchema):
    reason = fields.String(
        required=True,
        validate=validate.Length(min=3, max=500, error="Reason must be between 3 and 500 characters"),
        error_messages={"required": "Cancellation reason is required", "null": "Cancellation reason cannot be null"}
    )


class GetOrdersSchema(BaseSchema):
    page_size = fields.Integer(
        required=False, allow_none=False,
        load_default=20,
        validate=validate.Range(min=1, max=200, error="Page size must be between 1 and 200"),
        error_messages={"invalid": "Page size must be an integer"}
    )
    page_number = fields.Integer(
        required=False, allow_none=False,
        load_default=1,
        validate=validate.Range(min=1, error="Page number must be greater than 0"),
        error_messages={"invalid": "Page number must be an integer"}
    )
    status = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(ORDER_STATUSES, error="Invalid order status"),
        error_messages={"invalid": "Invalid order status"}
    )
    payment_status = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(PAYMENT_STATUSES, error="Invalid payment status"),
        error_messages={"invalid": "Invalid payment status"}
    )
    table_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Table Id must be greater than 0"),
        error_messages={"invalid": "Table Id must be an integer"}
    )
    customer_id = fields.Integer(
        required=False, allow_none=True,
        validate=validate.Range(min=1, error="Customer Id must be greater than 0"),
        error_messages={"invalid": "Customer Id must be an integer"}
    )
    ## Inclusive ISO date bounds on ordered_at
    from_date = fields.DateTime(required=False, allow_none=True)
    to_date = fields.DateTime(required=False, allow_none=True)
    search_value = fields.String(required=False, allow_none=True, validate=validate.Length(min=0))

    @validates_schema
    def validate_date_range(self, data, **kwargs):
        from_date = data.get("from_date")
        to_date = data.get("to_date")
        if from_date and to_date and to_date < from_date:
            raise ValidationError(
                "to_date must be on or after from_date",
                field_name="to_date"
            )