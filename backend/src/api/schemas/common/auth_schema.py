from marshmallow import fields, validate
from src.api.models.common.user_model import User
from src.api.schemas.common.base import BaseSchema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from src.api.schemas.mixins.otp_mixin import OTPFieldMixin
from src.api.schemas.mixins.name_mixin import NameFieldsMixin
from src.api.schemas.mixins.email_mixin import EmailFieldMixin
from src.api.schemas.mixins.password_mixin import PasswordUpdateMixin, PasswordVerifyMixin


class RegisterUserSchema(BaseSchema, NameFieldsMixin, EmailFieldMixin, PasswordUpdateMixin):
    pass

class VerifyEmailSchema(BaseSchema, EmailFieldMixin, OTPFieldMixin):
    pass

class LoginSchema(BaseSchema, EmailFieldMixin, PasswordVerifyMixin):
    pass

class SendOtpOnEmailSchema(BaseSchema, EmailFieldMixin):
    otp_type = fields.String(
        required=True,
        validate=validate.OneOf(
            ["account_activation", "email_verification", "reset_password"],
            error="OTP-Type must be either 'account_activation' or 'email_verification' or 'reset_password'"
        ),
        error_messages={
            "required": "OTP-Type is required"
        }
    )

class ActivateAccountSchema(BaseSchema, EmailFieldMixin, OTPFieldMixin):
    pass

class ResetPasswordSchema(BaseSchema, EmailFieldMixin, OTPFieldMixin, PasswordUpdateMixin):
    pass

class LoginResponseSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        include_relationships = False
        exclude = ("password",)  ## never return password
    role_id = fields.Int()
    role_name = fields.Method("get_role_name")
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    def get_role_name(self, obj):
        return obj.role.role_name if obj.role else None