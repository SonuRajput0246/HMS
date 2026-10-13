from src.api.schemas.fields.name import name_field


class NameFieldsMixin:
    first_name = name_field("First name")
    last_name = name_field("Last name")