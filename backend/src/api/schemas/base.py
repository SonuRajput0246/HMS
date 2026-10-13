from marshmallow import Schema, EXCLUDE, pre_load, ValidationError


class BaseSchema(Schema):
    """
    Base schema to apply common behavior across all schemas
    """
    class Meta:
        unknown = EXCLUDE

    OPTIONAL_FIELDS =  (
        "reservation_status",
        "search_room_number_value",
        "search_value",
        "deactivation_reason",
        "deletion_reason",
        "view",
        "notes"
    )

    @pre_load
    def normalize_strings(self, data, **kwargs):
        """
        Trim all string fields and reject whitespace-only values
        """
        errors = {}

        for key, value in data.items():
            if isinstance(value, str):
                trimmed = value.strip()

                if trimmed == "" and key in self.OPTIONAL_FIELDS:
                    data[key] = None
                    continue

                data[key] = trimmed

                if trimmed == "" and key not in self.OPTIONAL_FIELDS:
                    formatted_key = key.replace("_", " ").title()
                    errors[key] = [f"{formatted_key} cannot be empty or only spaces."]

        if errors:
            raise ValidationError(errors)

        return data
