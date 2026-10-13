from marshmallow import fields, validate

def phone_number_field(required: bool = True):
    return fields.String(
        required=required,
        validate=[
            # 1. Length validation to match DB String(20)
            validate.Length(
                min=10,
                max=20,
                error="Phone number must be between 10 and 20 characters"
            ),
            # 2. Regex to ensure only digits, spaces, hyphens, and the plus sign
            validate.Regexp(
                r'^\+?1?\d{9,15}$',
                error="Invalid phone number format"
            )
        ],
        error_messages={
            "required": "Phone number is required"
        }
    )