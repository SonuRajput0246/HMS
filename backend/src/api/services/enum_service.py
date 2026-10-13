from src.api.models import EnumDefinition, EnumOption


## Column -> enum_key bindings.
##
## The seeder is the single source of truth for which options exist. This map
## only records WHICH enum backs a given column, because a name cannot be
## derived from the column name (users.deactivated_by is backed by the
## 'account_deactivated_by' enum, for example).
##
## Adding a new OPTION never touches this map. Adding a new enum-backed COLUMN
## is one line here.
ENUM_COLUMN_BINDINGS = {
    ("users", "deactivated_by"): "account_deactivated_by",
    ("account_deletions", "account_deletion_status"): "account_deletion_status",
    ("account_deletions", "account_deleted_by"): "account_deleted_by",
    ("guests", "id_type"): "guests_id_type",
    ("additional_guests", "id_type"): "guests_id_type",
    ("rooms", "room_status"): "room_status",
    ("reservations", "reservation_status"): "reservation_status",
    ("payments", "payment_type"): "payment_type",
    ("payments", "payment_method"): "payment_method",
    ("payments", "payment_status"): "payment_status",
}


class EnumService:
    """
    Single validation mechanism for every enum-backed column in the app.

    Options live in enum_definitions / enum_options and are seeded from
    src/database/seeders/enum_seeder.py. To add an option you edit the seeder
    and rerun it - no model, migration, or service change is required.

    Usage in a service:

        enum_service = EnumService(db)
        error = enum_service.validate("account_deactivated_by", value)
        if error:
            return service_response(False, error, None, 400)
    """

    def __init__(self, db):
        self.db = db

    ## CACHE
    # Options are loaded once per request (per session) and reused, so a
    # payload touching five enum-backed columns still runs one query per enum
    # instead of five. The cache lives on the scoped session, which the app
    # removes in its teardown, so a reseeded option is picked up immediately
    # on the next request and never goes stale within one.
    @property
    def _cache(self) -> dict:
        info = self.db.info
        if "_enum_option_cache" not in info:
            info["_enum_option_cache"] = {}
        return info["_enum_option_cache"]

    def _active_option_keys(self, enum_key: str) -> list[str]:
        """Active, non-deleted option keys for one enum."""
        cache = self._cache
        if enum_key not in cache:
            definition = (
                self.db.query(EnumDefinition)
                .filter(
                    EnumDefinition.enum_key == enum_key,
                    EnumDefinition.is_deleted == False,
                )
                .first()
            )

            if definition is None:
                # Cache the empty list too, so an unknown enum is one query per
                # request rather than one per validation call.
                cache[enum_key] = []
            else:
                options = (
                    self.db.query(EnumOption.option_key)
                    .filter(
                        EnumOption.enum_id == definition.id,
                        EnumOption.is_deleted == False,
                        EnumOption.is_active == True,
                    )
                    .all()
                )
                cache[enum_key] = [row[0] for row in options]

        return cache[enum_key]

    ## VALIDATION

    def validate(self, enum_key: str, value, allow_none: bool = True):
        """
        Returns None when the value is acceptable, otherwise an error message.

        A None value passes unless allow_none is False, matching the nullable
        flag of the column being written.
        """
        if value is None:
            if allow_none:
                return None
            return f"'{enum_key}' is required."

        if not isinstance(value, str):
            return f"Invalid value for '{enum_key}'. Expected a string."

        valid_keys = self._active_option_keys(enum_key)

        # An empty list means the enum itself is missing or has no active
        # options. That is a data problem, not a bad request, so it is reported
        # distinctly instead of leaking the user a misleading "invalid value".
        if not valid_keys:
            return (
                f"Enum '{enum_key}' is not configured. "
                "Run the enum seeder to populate its options."
            )

        if value not in valid_keys:
            return (
                f"Invalid value '{value}' for '{enum_key}'. "
                f"Allowed: {', '.join(valid_keys)}."
            )

        return None

    def validate_model(self, table_name: str, values: dict):
        """
        Validates a dict of column -> value for one table, using
        ENUM_COLUMN_BINDINGS. Unregistered columns are ignored.

        Returns a dict of column -> error message for the fields that failed,
        so one 400 can report every bad field rather than the first.
        """
        errors = {}

        for column, value in values.items():
            enum_key = ENUM_COLUMN_BINDINGS.get((table_name, column))
            if enum_key is None:
                continue

            error = self.validate(enum_key, value)
            if error:
                errors[column] = error

        return errors