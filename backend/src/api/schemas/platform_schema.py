from marshmallow import fields, validate

from src.api.schemas.base import BaseSchema
from src.api.schemas.fields.email import email_field
from src.api.schemas.fields.password import update_password_field
from src.api.schemas.mixins.email_mixin import EmailFieldMixin
from src.api.schemas.mixins.password_mixin import PasswordUpdateMixin, PasswordVerifyMixin


class PlatformLoginSchema(BaseSchema, EmailFieldMixin, PasswordVerifyMixin):
    pass


class CreateTenantSchema(BaseSchema):
    ## Mirrors the model's ck_tenant_slug_format. A slug that is not a DNS label
    ## stops resolving, and the failure looks like an outage rather than a bad
    ## input, so it is refused here with a message that says what a slug is.
    slug = fields.String(
        required=True,
        allow_none=False,
        validate=validate.Regexp(
            r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$",
            error="Slug must be a lowercase DNS label: letters, digits, and "
                  "interior hyphens only.",
        ),
        error_messages={"required": "Slug is required", "null": "Slug cannot be null"},
    )
    name = fields.String(
        required=True,
        allow_none=False,
        validate=validate.Length(
            min=1, max=150, error="Name must be between 1 and 150 characters"
        ),
        error_messages={"required": "Name is required", "null": "Name cannot be null"},
    )
    admin_email = email_field()
    admin_password = update_password_field("Admin password")


class SuspendTenantSchema(BaseSchema):
    reason = fields.String(
        required=True,
        allow_none=False,
        validate=validate.Length(
            min=1, max=255, error="Reason must be between 1 and 255 characters"
        ),
        error_messages={"required": "Reason is required", "null": "Reason cannot be null"},
    )


class ResetTenantAdminPasswordSchema(BaseSchema, PasswordUpdateMixin):
    pass
