from src.api.schemas.fields.email import email_field


class EmailFieldMixin:
    email = email_field()