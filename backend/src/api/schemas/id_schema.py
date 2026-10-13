from marshmallow import fields, validate
from src.api.schemas.base import BaseSchema


def id_schema_factory(
    field_name: str,
    label: str = "Id",
    min_value: int = 1,
    required: bool = True
):
    return type(
        f"{label.replace(' ', '')}Schema",
        (BaseSchema,),
        {
            field_name: fields.Int(
                required=required,
                allow_none=False,
                validate=validate.Range(
                    min=min_value,
                    error=f"{label} must be greater than or equal to {min_value}"
                ),
                error_messages={
                    "required": f"{label} is required.",
                    "null": f"{label} cannot be null.",
                    "invalid": f"Invalid {label}."
                },
            )
        },
    )












# from marshmallow import fields, validate
# from src.api.schemas.base import BaseSchema
#
#
# def id_schema_factory(field_name: str, label: str = "Id"):
#     return type(
#         f"{label.replace(' ', '')}Schema",
#         (BaseSchema,),
#         {
#             field_name: fields.Int(
#                 required=True,
#                 allow_none=False,
#                 validate=validate.Range(
#                     min=1,
#                     error=f"{label} must be greater than 0"
#                 ),
#                 error_messages={
#                     "required": f"{label} is required.",
#                     "null": f"{label} cannot be null.",
#                     "invalid": f"Invalid {label}."
#                 },
#             )
#         },
#     )
