from src.api.schemas.fields.password import verify_password_field, update_password_field


class PasswordUpdateMixin:
    password = update_password_field("Password")

class PasswordVerifyMixin:
    password = verify_password_field("Password")