from marshmallow import fields, validate, validates_schema, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from src.api.models.super_admin_user_model import SuperAdminUser
from src.api.schemas.base import BaseSchema
from src.api.schemas.fields.email import email_field
from src.api.schemas.fields.password import update_password_field, verify_password_field
from src.api.schemas.mixins.email_mixin import EmailFieldMixin
from src.api.schemas.mixins.name_mixin import NameFieldsMixin
from src.api.schemas.mixins.password_mixin import PasswordVerifyMixin
from src.api.schemas.pagination_schema import PaginationSchema


## The 6-digit TOTP an authenticator app produces. Matched as a literal regex
## rather than a length rule alone so "12345" and "1234567" are both refused
## before the secret is ever compared.
TOTP_REGEX = r"^\d{6}$"


def totp_field(label: str = "Verification code"):
    return fields.String(
        required=True,
        allow_none=False,
        validate=validate.Regexp(
            regex=TOTP_REGEX,
            error=f"{label} must be a 6-digit number",
        ),
        error_messages={
            "required": f"{label} is required",
            "null": f"{label} cannot be null",
        },
    )


class SuperAdminLoginSchema(BaseSchema, EmailFieldMixin, PasswordVerifyMixin):
    """Platform sign-in. Same field construction as the hotel LoginSchema so
    both screens enforce the same password rules; it is a distinct class because
    it is a distinct endpoint and a distinct population."""
    pass


class SuperAdminResponseSchema(SQLAlchemyAutoSchema):
    """Wire shape for a platform admin.

    `password` and `mfa_secret` are both excluded -- they are the two columns
    that must never leave the server.
    """
    class Meta:
        model = SuperAdminUser
        load_instance = True
        include_relationships = False
        exclude = ("password", "mfa_secret")


## ---------------------------------------------------------- change password
class SuperAdminChangePasswordSchema(BaseSchema):
    """Self-service password change for the signed-in platform admin.

    Mirrors the hotel `UpdatePasswordSchema` field-for-field so both consoles
    enforce the same rules. The caller is known from the token, so there is no
    user id in the body -- unlike the hotel schema, which the account service
    resolves the same way.
    """
    current_password = verify_password_field("Current password")
    new_password = update_password_field("New password")

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        current = data.get("current_password")
        new = data.get("new_password")

        if current and new and current == new:
            raise ValidationError(
                "New password must be different from current password",
                field_name="new_password",
            )


## ---------------------------------------------------------------------- MFA
class SuperAdminVerifyMfaSchema(BaseSchema):
    """The second step of sign-in once MFA is enabled on the account.

    `temp_token` is the short-lived `super_admin_mfa_pending` token minted by
    login; it is the only thing that ties this request to the password that was
    just proven, so it travels with the code.
    """
    temp_token = fields.String(
        required=True,
        allow_none=False,
        error_messages={
            "required": "Temporary token is required",
            "null": "Temporary token cannot be null",
        },
    )
    totp = totp_field()


class SuperAdminEnableMfaSchema(BaseSchema):
    """Confirm a freshly enrolled authenticator before switching MFA on."""
    totp = totp_field()


## ------------------------------------------------------- admin management
class ListSuperAdminsSchema(PaginationSchema):
    """Operator list. A status facet so the console can show active vs
    deactivated accounts without inventing a second filter."""
    status = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(
            ["active", "inactive"],
            error="Status must be 'active' or 'inactive'.",
        ),
    )


class CreateSuperAdminSchema(BaseSchema, NameFieldsMixin):
    """Add a new platform operator.

    The password is set out of band by the creating admin rather than through an
    invite link (the same product choice the tenant create form makes), and is
    only ever stored hashed.
    """
    email = email_field()
    password = update_password_field("Password")


class UpdateSuperAdminSchema(BaseSchema):
    """Partial profile edit for an operator. Everything optional so a screen can
    submit one field; the service only touches what is present."""
    first_name = fields.String(
        required=False, allow_none=False,
        validate=validate.Length(min=1, max=50, error="First name must be between 1 and 50 characters long"),
    )
    last_name = fields.String(
        required=False, allow_none=False,
        validate=validate.Length(min=1, max=50, error="Last name must be between 1 and 50 characters long"),
    )
    email = email_field(required=False)


class SuperAdminStatusSchema(BaseSchema):
    """Activate/deactivate an operator. One boolean, read as a verb."""
    is_active = fields.Boolean(
        required=True,
        error_messages={"required": "is_active is required", "null": "is_active cannot be null"},
    )


class ResetSuperAdminPasswordSchema(BaseSchema):
    """Set a new password on an operator's behalf. Used for recovery by another
    admin; an admin changing their own password uses the self-service change
    instead, which requires the current one."""
    new_password = update_password_field("New password")


## --------------------------------------------------------------- audit log
class ListAuditLogsSchema(PaginationSchema):
    """Platform activity feed query.

    Every filter is optional and additive: no filter means "everything, newest
    first", and the two indexes on `audit_logs` (`ix_audit_entity`,
    `ix_audit_actor`) are exactly what the entity/actor filters address.
    """
    action = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=50, error="Action must be 50 characters or less"),
    )
    entity_type = fields.String(
        required=False, allow_none=True,
        validate=validate.Length(max=50, error="Entity type must be 50 characters or less"),
    )
    entity_id = fields.Integer(
        required=False, allow_none=True,
        error_messages={"invalid": "entity_id must be an integer."},
    )
    super_admin_id = fields.Integer(
        required=False, allow_none=True,
        error_messages={"invalid": "super_admin_id must be an integer."},
    )
    date_from = fields.DateTime(
        required=False, allow_none=True,
        error_messages={"invalid": "date_from must be an ISO-8601 timestamp."},
    )
    date_to = fields.DateTime(
        required=False, allow_none=True,
        error_messages={"invalid": "date_to must be an ISO-8601 timestamp."},
    )
