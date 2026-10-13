from marshmallow import fields, validate
from typing import List, Callable


def text_field(max_len, min_len=None, required=False, allow_none=True, regex=None, label=""):

    validators: List[Callable] = [validate.Length(max=max_len)]

    if min_len is not None:
        validators.append(validate.Length(min=min_len))

    if regex:
        validators.append(validate.Regexp(regex))

    return fields.String(
        required=required,
        allow_none=allow_none,
        validate=validators,
        error_messages={
            "required": f"{label} is required",
            "null": f"{label} cannot be null",
            "invalid": f"Invalid {label}"
        }
    )
