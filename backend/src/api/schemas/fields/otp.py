from marshmallow import validate, fields


def otp_field(label: str = "OTP", required: bool = True):
    return fields.String(
        required=required,
        allow_none=False,
        validate=[
            validate.Length(
                equal=6,
                error=f"{label} must be exactly of 6 digits long"
            ),
            validate.Regexp(
                regex=r"^\d{6}$",
                error="OTP must contain only numbers"
            )
        ],
        error_messages={
            "required": "OTP is required",
            "null": "OTP cannot be null"
        }
    )