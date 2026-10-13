from marshmallow import fields, validate, validates_schema, ValidationError
from src.api.schemas.base import BaseSchema
from src.api.schemas.id_schema import id_schema_factory
from src.api.schemas.mixins.name_mixin import NameFieldsMixin
from src.api.schemas.fields.password import update_password_field

GetUserByIdSchema = id_schema_factory("id", "User Id")

UpsertUserIdSchema = id_schema_factory("id", "Role Id", min_value=0, required=True)
UpsertUserRoleIdSchema = id_schema_factory("role_id", "Role Id", min_value=1, required=True)

class UpsertUserSchema(UpsertUserIdSchema, NameFieldsMixin, UpsertUserRoleIdSchema):
    email = fields.Email(
        required=False,
        allow_none=True,
        error_messages={"invalid": "Invalid email address"}
    )
    # Reuses the shared field rather than repeating the rule. This one declared
    # its own `validate.Length(min=1, max=20)` while every other password entry
    # point -- registration, reset, change-your-own -- goes through
    # update_password_field and so enforces PASSWORD_MIN_LENGTH (6). An admin
    # could therefore create a user with a one-character password that the same
    # user could not have set for themselves.
    password = update_password_field("Password", required=False)
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)
    @validates_schema
    def validate_insert_update_rules(self, data, **kwargs):
        user_id = data.get("id", 0)

        # INSERT case
        if user_id == 0:
            if not data.get("email"):
                raise ValidationError(
                    {"email": ["Email is required for creating user"]}
                )
            if not data.get("password"):
                raise ValidationError(
                    {"password": ["Password is required for creating user"]}
                )

        # UPDATE case
        if user_id > 0:
            # Optional: prevent email change if your business rules require
            pass
