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

    def clear_cache(self):
        """Drop cached options. Call after seeding within a live session."""
        self.db.info.pop("_enum_option_cache", None)

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

    def is_valid(self, enum_key: str, value) -> bool:
        """True when value is an active option of enum_key."""
        if value is None:
            return True
        return value in self._active_option_keys(enum_key)

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

    def validate_many(self, values: dict):
        """
        Validates several values at once.

        values maps a column name to either a raw value, or to a
        (value, enum_key) pair. Returns a dict of column -> error message for
        the fields that failed, so a single 400 can report every bad field.
        """
        errors = {}

        for column, spec in values.items():
            if isinstance(spec, tuple):
                value, enum_key = spec
            else:
                value = spec
                enum_key = self.enum_key_for_column(column)

                if enum_key is None:
                    # Not a registered enum column; nothing to check.
                    continue

            error = self.validate(enum_key, value)
            if error:
                errors[column] = error

        return errors

    def enum_key_for_column(self, column: str):
        """
        Resolve the enum_key backing a bare column name.

        Only unambiguous names resolve: 'id_type' maps to two tables, so it is
        rejected and the caller must pass the (table, column) pair.
        """
        matches = {
            enum_key
            for (table, col), enum_key in ENUM_COLUMN_BINDINGS.items()
            if col == column
        }
        ## 'room_status' is registered against rooms.room_status, so a bare
        ## name can be ambiguous only when two tables bind the same column
        ## name to different enums.

        if len(matches) == 1:
            return matches.pop()
        return None

    def validate_model(self, table_name: str, values: dict):
        """
        Validates a dict of column -> value for one table, using
        ENUM_COLUMN_BINDINGS. Unregistered columns are ignored.
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

    ## LABELS

    def get_option(self, enum_key: str, option_key: str):
        """One option with its display data, or None."""
        if option_key is None:
            return None

        return (
            self.db.query(EnumOption)
            .join(EnumDefinition, EnumOption.enum_id == EnumDefinition.id)
            .filter(
                EnumDefinition.enum_key == enum_key,
                EnumDefinition.is_deleted == False,
                EnumOption.option_key == option_key,
                EnumOption.is_deleted == False,
            )
            .first()
        )

    def get_label(self, enum_key: str, option_key: str):
        """Display label for an option, falling back to the key itself.

        Falling back keeps an API response readable when a row references an
        option that was later deactivated, instead of returning a bare null.
        """
        if option_key is None:
            return None

        option = self.get_option(enum_key, option_key)
        return option.option_label if option else option_key

    def get_labels(self, enum_key: str, column: str, value):
        """
        Display label for a column value. Returns None when value is None, so
        callers can spread this into a response dict unconditionally.
        """
        if value is None:
            return None
        return self.get_label(enum_key, value)