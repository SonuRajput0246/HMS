"""Single reader for the `enum_definitions` / `enum_options` tables.

Every enum-backed column in the app resolves its allowed values through
`EnumHelper`, so exactly one place knows how these two tables are shaped.

WHY THERE IS NO FALLBACK LIST
-----------------------------
An earlier version of this read a hardcoded allow-list when the table could not
be reached. That turns the Python file into a second source of truth: an admin
adds an option in the UI, the table says yes and the code says no, and the two
drift apart silently. It also defeats validation on the write paths -- accepting
a value the table rejected is worse than failing loudly. So an unreachable or
unseeded table raises `EnumUnavailableError` and the caller decides what to do.

NOTE ON DEFAULTS
----------------
`default_value` returns the option flagged `is_default`. That is the right
answer for "what state does a new row start in", and the wrong answer for "which
specific state does this transition target" -- see the lifecycle constants in
reservation_service.py for those.
"""
import logging

from src.api.models.enum_definitions_model import EnumDefinition
from src.api.models.enum_options_model import EnumOption


logger = logging.getLogger(__name__)


class EnumUnavailableError(RuntimeError):
    """The enum tables could not supply a value list.

    Infrastructure fault (unseeded database, unreachable table), not bad input.
    Callers on an admin write path should turn this into a 503 rather than a
    validation error, so the operator knows to run the seeder.
    """


class EnumHelper:
    def __init__(self, db):
        self.db = db
        self._values_cache: dict[str, tuple[str, ...]] = {}
        self._default_cache: dict[str, str] = {}

    def active_values(self, enum_key: str) -> tuple[str, ...]:
        """Active, non-deleted option keys for one enum definition.

        Ordered by `sort_order` so a caller presenting them as a dropdown gets
        the seeded order for free.

        Raises EnumUnavailableError if the definition is missing or has no
        active options -- both mean the seeder has not been run for this key.
        """
        if enum_key not in self._values_cache:
            definition = self._definition(enum_key)
            options = (
                self.db.query(EnumOption)
                .filter(
                    EnumOption.enum_id == definition.id,
                    EnumOption.is_deleted == False,
                    EnumOption.is_active == True,
                )
                .order_by(EnumOption.sort_order.asc())
                .all()
            )
            if not options:
                raise EnumUnavailableError(
                    f"Enum '{enum_key}' has no active options. Run the enum seeder."
                )
            self._values_cache[enum_key] = tuple(
                str(option.option_key).strip().lower() for option in options
            )

        return self._values_cache[enum_key]

    def default_value(self, enum_key: str) -> str:
        """The option flagged `is_default` for one enum definition.

        Used for "what state does a new row start in" -- e.g. a new booking
        begins at the default `reservation_status`, a new room at the default
        `room_status`.
        """
        if enum_key not in self._default_cache:
            definition = self._definition(enum_key)
            option = (
                self.db.query(EnumOption)
                .filter(
                    EnumOption.enum_id == definition.id,
                    EnumOption.is_deleted == False,
                    EnumOption.is_active == True,
                    EnumOption.is_default == True,
                )
                .order_by(EnumOption.sort_order.asc())
                .first()
            )
            if not option:
                raise EnumUnavailableError(
                    f"Enum '{enum_key}' has no default option. Mark one active in "
                    f"enum_options, or hardcode the state if it is a fixed transition."
                )
            self._default_cache[enum_key] = str(option.option_key).strip().lower()

        return self._default_cache[enum_key]

    def normalise(self, value, enum_key: str) -> str | None:
        """Bare value for a String column, or None when not an active option.

        Case- and whitespace-insensitive. Raises EnumUnavailableError if the
        allow-list itself cannot be read.
        """
        if value is None:
            return None

        text = str(getattr(value, "value", value)).strip().lower()
        if not text:
            return None

        return text if text in self.active_values(enum_key) else None

    def _definition(self, enum_key: str):
        definition = (
            self.db.query(EnumDefinition)
            .filter(
                EnumDefinition.enum_key == enum_key,
                EnumDefinition.is_deleted == False,
            )
            .first()
        )
        if not definition:
            raise EnumUnavailableError(
                f"Enum definition '{enum_key}' is missing. Run the enum seeder."
            )
        return definition