from marshmallow import ValidationError
from src.api.models import EnumDefinition, EnumOption
from src.database.session import db_session


def enum_option(enum_key: str, allow_none: bool = True):
    """
    Marshmallow validator that checks a value against enum_options.

    Used on a schema field so an invalid value becomes a 400 through the
    existing Marshmallow error handler, before the service layer runs:

        deactivation_reason = fields.String(
            validate=enum_option("account_deactivated_by"),
        )

    Note this opens its own short-lived session, because schema validation
    runs outside the service's session. For several fields on one payload,
    prefer EnumService.validate_many in the service, which reuses a single
    session and a per-request cache.
    """

    def _validate(value):
        if value is None:
            if allow_none:
                return
            raise ValidationError(f"'{enum_key}' is required.")

        if not isinstance(value, str):
            raise ValidationError(
                f"Invalid value for '{enum_key}'. Expected a string."
            )

        db = db_session()

        definition = (
            db.query(EnumDefinition)
            .filter(
                EnumDefinition.enum_key == enum_key,
                EnumDefinition.is_deleted == False,
            )
            .first()
        )

        if definition is None:
            raise ValidationError(
                f"Enum '{enum_key}' is not configured. "
                "Run the enum seeder to populate its options."
            )

        valid_keys = [
            row[0]
            for row in db.query(EnumOption.option_key)
            .filter(
                EnumOption.enum_id == definition.id,
                EnumOption.is_deleted == False,
                EnumOption.is_active == True,
            )
            .all()
        ]

        if not valid_keys:
            raise ValidationError(
                f"Enum '{enum_key}' has no active options. "
                "Run the enum seeder to populate its options."
            )

        if value not in valid_keys:
            raise ValidationError(
                f"Invalid value '{value}' for '{enum_key}'. "
                f"Allowed: {', '.join(valid_keys)}."
            )

    return _validate