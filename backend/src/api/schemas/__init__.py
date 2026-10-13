"""Marshmallow schemas.

Do NOT import every module here. Several schemas import each other and some
reach into models that reference back, so eager imports create cycles.

Import the specific module you need directly:

    from src.api.schemas.common_schema import GetAllStatesSchema

Sub-packages:

    fields/      reusable field factories (email, phone, password, otp, ...)
    mixins/      reusable field mixins the factories compose
    validators/  cross-field validators shared by schemas
"""