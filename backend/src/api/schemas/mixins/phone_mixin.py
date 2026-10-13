from src.api.schemas.fields.phone import phone_number_field


class PhoneNumberFieldMixin:
    phone = phone_number_field()