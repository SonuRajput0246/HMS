"""Single source of truth for template codes and placeholder names.

Both the seeder (src/database/seeders/template_seeder.py) and the send path
(src/api/services/email_service.py) import from here, so a code is never
spelled out as a raw string in two places.

`code` is the stable contract that the database stores in
`message_templates.code` and that backend services resolve against. The `code`
column is protected from edits on seeded rows (see `is_system` and the guard in
template_service.py), so these values only change alongside a dedicated
migration.

NOTE: this enum is NOT persisted as a SQLAlchemy column type. `channel` is the
only enumerated column on the table, and it is a plain String validated against
the `template_channel` rows in `enum_definitions`.
"""
from enum import Enum


class TemplateCode(str, Enum):
    """Event codes for the DB-driven template store."""

    EMAIL_VERIFICATION_OTP = "EMAIL_VERIFICATION_OTP"
    ACCOUNT_ACTIVATION_OTP = "ACCOUNT_ACTIVATION_OTP"
    PASSWORD_RESET_OTP = "PASSWORD_RESET_OTP"


class TemplateVariable(str, Enum):
    """Well-known placeholder names.

    Stored in `message_templates.variables` so the CRUD API can validate
    admin-submitted templates and the Angular editor can offer an
    insert-variable helper plus a live preview.
    """

    USER_NAME = "user_name"
    OTP = "otp"
    EXPIRY_MINUTES = "expiry_minutes"
    ## The current hotel's brand. Supplied by `email_service` from the tenant's
    ## `system_settings`, so seeded copy can sign off as the hotel rather than as
    ## the product.
    COMPANY_NAME = "company_name"


## The three OTP flows carry the same context, so every seeded template uses
## this exact variable set. Kept here to avoid repeating the list six times.
OTP_VARIABLES = [
    TemplateVariable.USER_NAME.value,
    TemplateVariable.OTP.value,
    TemplateVariable.EXPIRY_MINUTES.value,
    TemplateVariable.COMPANY_NAME.value,
]


def all_codes() -> list[str]:
    """Every known code as plain strings, for the seeder and for validation."""
    return [code.value for code in TemplateCode]


def is_known_code(code: str) -> bool:
    """Guard for admin-created rows: is this code one the app ships with?"""
    return code in all_codes()


def default_sort_order(code: str) -> int:
    """Stable display order so the admin list is not insertion-order dependent."""
    try:
        return all_codes().index(code) * 10
    except ValueError:
        ## Admin-created codes sort after the seeded ones
        return len(TemplateCode) * 10