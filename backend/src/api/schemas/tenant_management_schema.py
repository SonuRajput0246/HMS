from marshmallow import fields, validate

from src.api.schemas.base import BaseSchema
from src.api.schemas.fields.email import email_field
from src.api.schemas.fields.password import update_password_field
from src.api.schemas.mixins.password_mixin import PasswordUpdateMixin
from src.api.schemas.pagination_schema import PaginationSchema


## The slug becomes a subdomain: `grandcentral` is reached at
## grandcentral.localhost. Lowercase, digits and hyphens, not starting or ending
## with a hyphen, so it is a valid DNS label and a readable URL. 2..63 matches
## the column and ck_tenant_slug_format on the model.
SLUG_REGEX = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"

CURRENCY_REGEX = r"^[A-Za-z]{3}$"


class ListTenantsSchema(PaginationSchema):
    """Tenant list query. Adds a status facet on top of the shared pagination.

    `status` is a facet rather than two booleans so the UI's Active/Inactive/
    Archived tabs map onto exactly one filter each, and an unrecognised value is
    rejected instead of silently ignored.
    """
    status = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(
            ["active", "inactive", "archived"],
            error="Status must be 'active', 'inactive' or 'archived'.",
        ),
    )


def _slug_field(required: bool):
    return fields.String(
        required=required,
        allow_none=False,
        validate=[
            validate.Length(
                min=2, max=63,
                error="Slug must be between 2 and 63 characters long",
            ),
            validate.Regexp(
                regex=SLUG_REGEX,
                error=(
                    "Slug must be lowercase letters, numbers and hyphens, "
                    "and must start and end with a letter or number"
                ),
            ),
        ],
        error_messages={
            "required": "Slug is required",
            "null": "Slug cannot be null",
        },
    )


def _timezone_field(required: bool):
    return fields.String(
        required=required,
        allow_none=False,
        validate=validate.Length(
            min=1, max=50,
            error="Timezone must be between 1 and 50 characters long",
        ),
        error_messages={
            "required": "Timezone is required",
            "null": "Timezone cannot be null",
        },
    )


def _currency_field(required: bool):
    return fields.String(
        required=required,
        allow_none=False,
        validate=validate.Regexp(
            regex=CURRENCY_REGEX,
            error="Currency must be a 3-letter ISO 4217 code",
        ),
        error_messages={
            "required": "Currency is required",
            "null": "Currency cannot be null",
        },
    )


class CreateTenantSchema(BaseSchema):
    """Register a hotel and its first administrator in one call.

    The administrator's fields are named with an `admin_` prefix rather than
    being nested, because the screen that gathers them is one form: keeping them
    flat means the payload the browser sends has no invented shape.

    `admin_password` is required and only ever stored hashed. The alternative
    -- an invite link the operator sets it through -- is not part of the current
    product, so the platform admin hands the credentials over out of band.
    """
    name = fields.String(
        required=True, allow_none=False,
        validate=validate.Length(min=1, max=150, error="Name must be between 1 and 150 characters long"),
        error_messages={"required": "Name is required", "null": "Name cannot be null"},
    )
    slug = _slug_field(required=True)
    timezone = _timezone_field(required=True)
    currency = _currency_field(required=True)

    admin_first_name = fields.String(
        required=True, allow_none=False,
        validate=validate.Length(min=1, max=50, error="Admin first name must be between 1 and 50 characters long"),
        error_messages={"required": "Admin first name is required", "null": "Admin first name cannot be null"},
    )
    admin_last_name = fields.String(
        required=True, allow_none=False,
        validate=validate.Length(min=1, max=50, error="Admin last name must be between 1 and 50 characters long"),
        error_messages={"required": "Admin last name is required", "null": "Admin last name cannot be null"},
    )
    admin_email = email_field()
    admin_password = update_password_field("Admin password")


class UpdateTenantSchema(BaseSchema):
    """Partial edit. Everything optional so a screen can submit one changed
    field; the service only touches what is actually present.

    `slug` is deliberately included: it is the tenant's URL, so changing it moves
    the hotel to a different subdomain. The service treats that as the sensitive
    change it is and reports it in the audit log.
    """
    name = fields.String(required=False, allow_none=False,
                         validate=validate.Length(min=1, max=150, error="Name must be between 1 and 150 characters long"))
    slug = _slug_field(required=False)
    timezone = _timezone_field(required=False)
    currency = _currency_field(required=False)


class TenantStatusSchema(BaseSchema):
    """Activate/deactivate body. One boolean, read as a verb by the caller."""
    is_active = fields.Boolean(
        required=True,
        error_messages={"required": "is_active is required", "null": "is_active cannot be null"},
    )


class ResetTenantAdminPasswordSchema(BaseSchema, PasswordUpdateMixin):
    """Recovery for a hotel whose only admin has lost their password.

    Not part of the CMS console's surface: there, a locked-out hotel is an
    in-product problem. Here it is only solvable from outside, so the operator
    gets an explicit endpoint rather than having to sign in as that admin.
    """
    pass
