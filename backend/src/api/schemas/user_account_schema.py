from marshmallow import fields, validate, validates_schema, ValidationError
from src.api.schemas.base import BaseSchema
from src.api.schemas.fields.password import verify_password_field, update_password_field
from src.api.schemas.mixins.name_mixin import NameFieldsMixin
from src.api.schemas.mixins.password_mixin import PasswordVerifyMixin


class UpdateUserProfileSchema(BaseSchema, NameFieldsMixin):
    pass

class UpdatePasswordSchema(BaseSchema):
    current_password = verify_password_field("Current password")
    new_password = update_password_field("New password")
    @validates_schema
    def validate_passwords(self, data, **kwargs):
        current = data.get("current_password")
        new = data.get("new_password")

        if current and new and current == new:
            raise ValidationError(
                "New password must be different from current password",
                field_name="new_password"
            )

class DeactivateMyAccountSchema(BaseSchema):
    deactivation_reason = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(
            max=255,
            error="Deleted reason must be 255 characters or less"
        )
    )


class DeleteMyAccountSchema(BaseSchema, PasswordVerifyMixin):
    deletion_reason = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(
            max=255,
            error="Deleted reason must be 255 characters or less"
        )
    )