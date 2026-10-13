"""Read-only resolver for the send path.

Separate from `template_service` (the admin CRUD surface used by the Angular
routes). This module has one job: turn a template `code` + `channel` into
rendered content for an outgoing email or in-app notification.

DESIGN RULES
------------
1. Never raises. A missing, inactive, or malformed template must degrade to
   fallback copy rather than fail a login, an activation, or a password reset.
   Callers inspect `is_fallback` / `found` and decide whether to log or alert.

2. No caching. One indexed SELECT per send is negligible next to an SMTP
   round-trip, and it means an admin edit in the UI takes effect on the very
   next send with no invalidation logic and no stale window. If this ever
   needs a cache, add it here alone -- `email_service` should not have to
   change.

3. `code` lookup is case-insensitive in practice: MySQL compares `code` with
   the table's `utf8mb4_0900_ai_ci` collation. Values that differ only in case
   resolve to the same row.

4. Valid channels are read from `enum_definitions` / `enum_options`
   (`enum_key` = 'template_channel', seeded by enum_seeder.py), not from a
   Python enum, so adding a delivery channel is a data change. The lookup is
   cached per resolver instance because one instance serves the whole send and
   the option list only changes on a re-seed.
"""
import logging

from src.api.models.template_model import Template
from src.api.models.enum_definitions_model import EnumDefinition
from src.api.utils.template_renderer import (
    render_email,
    render_in_app,
    render_fallback_email,
    audit_declared_variables,
)


logger = logging.getLogger(__name__)


## `enum_definitions.enum_key` holding the allowed delivery channels.
CHANNEL_ENUM_KEY = "template_channel"

## Channels that must always resolve, whatever the enum table says. Email is
## how OTP / activation / password-reset mails go out, so an empty or
## half-seeded enum table must degrade to a channel rather than block a login.
CORE_CHANNELS = ("email", "in_app")


class TemplateResolver:
    """Resolves template rows for sending. Read-only; performs no writes."""

    def __init__(self, db):
        self.db = db
        self._channel_cache: tuple[str, ...] | None = None


    # ---------------------------------------------------------------
    # LOOKUP
    # ---------------------------------------------------------------

    def _valid_channels(self) -> tuple[str, ...]:
        """Allowed channels, read once per instance from the enum tables."""
        if self._channel_cache is None:
            self._channel_cache = self._load_channels()
        return self._channel_cache

    def _load_channels(self) -> tuple[str, ...]:
        """`enum_options` keys for the template_channel enum definition.

        Never raises: a missing definition or a failed query falls back to the
        core channels, per the no-throw rule at the top of this module.
        """
        try:
            definition = (
                self.db.query(EnumDefinition)
                .filter(
                    EnumDefinition.enum_key == CHANNEL_ENUM_KEY,
                    EnumDefinition.is_deleted == False,
                )
                .first()
            )

            keys = [
                str(option.option_key).strip().lower()
                for option in (definition.options if definition else [])
                if option.is_deleted == False and option.is_active
            ]
        except Exception:
            logger.exception(
                "TemplateResolver: could not read '%s' options. Falling back to %s.",
                CHANNEL_ENUM_KEY, list(CORE_CHANNELS),
            )
            keys = []

        ## Union, not replacement: a new channel in the DB is accepted, but
        ## deactivating `email` in the admin UI cannot brick the auth mails.
        return tuple(dict.fromkeys([*keys, *CORE_CHANNELS]))

    def _normalise_channel(self, channel) -> str | None:
        """Accept an enum member, a string like 'email' / 'in_app', or None.

        Returns the channel as a plain string, or None when the value is not
        one of the options in the enum table.
        """
        if channel is None:
            return None

        text = str(getattr(channel, "value", channel)).strip().lower()
        if not text:
            return None

        return text if text in self._valid_channels() else None

    @staticmethod
    def _normalise_code(code) -> str:
        """Accept a `TemplateCode` member or a raw string."""
        return str(getattr(code, "value", code)).strip()

    def get_active(self, code, channel="email") -> Template | None:
        """The live, active row for this (code, channel), or None.

        Filters on `is_deleted` as well as `is_active` so a soft-deleted row
        is never resurrected by a send.
        """
        raw_code = self._normalise_code(code)
        enum_channel = self._normalise_channel(channel)
        if not raw_code or enum_channel is None:
            return None

        return (
            self.db.query(Template)
            .filter(
                Template.is_deleted == False,
                Template.is_active == True,
                Template.code == raw_code,
                Template.channel == enum_channel,
            )
            .first()
        )

    def get_any(self, code, channel="email") -> Template | None:
        """The row for this (code, channel) even if inactive/deleted.

        For diagnostics and admin tooling, not for sending.
        """
        raw_code = self._normalise_code(code)
        enum_channel = self._normalise_channel(channel)
        if not raw_code or enum_channel is None:
            return None

        return (
            self.db.query(Template)
            .filter(
                Template.code == raw_code,
                Template.channel == enum_channel,
            )
            .first()
        )

    def exists(self, code, channel="email") -> bool:
        """Cheap availability check used by the CRUD API and health checks."""
        return self.get_active(code, channel) is not None

    def is_suspended(self, code, channel="email") -> bool:
        """True when a row exists but has been switched off or soft-deleted.

        Lets an admin-facing error say "this template is inactive" instead of
        the misleading "not found".
        """
        return self.get_any(code, channel) is not None and not self.exists(code, channel)


    # ---------------------------------------------------------------
    # RENDERING
    # ---------------------------------------------------------------

    def render(self, code, context: dict, channel="email") -> dict:
        """Resolve and render in one call. Never raises.

        Returns a stable dict shape regardless of outcome:

            {
              "found": bool,          # an active row was used
              "is_fallback": bool,    # fallback copy was substituted
              "code": str,
              "channel": str,         # 'email' | 'in_app'
              "template_id": int | None,
              "version": int | None,
              "is_system": bool | None,
              "subject": str,         # email only
              "html_body": str,       # email only, wrapped in layout.html
              "content_html": str,    # email only, fragment on its own
              "title": str,           # in_app only
              "message": str,         # in_app only
              "used_variables": list[str],
              "missing_variables": list[str],
              "warnings": list[str],
            }
        """
        raw_code = self._normalise_code(code)
        enum_channel = self._normalise_channel(channel)

        if enum_channel is None:
            logger.error(
                "TemplateResolver: unknown channel %r for code %r", channel, raw_code
            )
            return self._empty_result(
                raw_code,
                str(channel),
                ["Unrecognised channel value."],
            )

        row = self.get_active(raw_code, enum_channel)

        if row is None:
            return self._handle_missing(raw_code, enum_channel)

        try:
            if enum_channel == "email":
                rendered = render_email(row, context or {})
                result = {
                    "found": True,
                    "is_fallback": False,
                    "code": raw_code,
                    "channel": enum_channel,
                    "template_id": row.id,
                    "version": row.version,
                    "is_system": row.is_system,
                    "subject": rendered["subject"],
                    "html_body": rendered["html_body"],
                    "content_html": rendered["content_html"],
                    "title": None,
                    "message": None,
                    "used_variables": rendered["used_variables"],
                    "missing_variables": rendered["missing_variables"],
                }
            else:
                rendered = render_in_app(row, context or {})
                result = {
                    "found": True,
                    "is_fallback": False,
                    "code": raw_code,
                    "channel": enum_channel,
                    "template_id": row.id,
                    "version": row.version,
                    "is_system": row.is_system,
                    "subject": None,
                    "html_body": None,
                    "content_html": None,
                    "title": rendered["title"],
                    "message": rendered["message"],
                    "used_variables": rendered["used_variables"],
                    "missing_variables": rendered["missing_variables"],
                }
        except Exception as exc:
            ## A template edited into something unrenderable must not break a
            ## send. Log loudly, then fall back.
            logger.exception(
                "TemplateResolver: render failed for %s/%s (template_id=%s)",
                raw_code, enum_channel, row.id,
            )
            return self._handle_missing(
                raw_code,
                enum_channel,
                reason=f"Render failed: {exc}",
                template_id=row.id,
            )

        result["warnings"] = self._collect_warnings(row, context or {}, result)
        self._log_warnings(result)
        return result

    def render_email(self, code, context: dict) -> dict:
        """Convenience wrapper pinned to the email channel."""
        return self.render(code, context, "email")


    # ---------------------------------------------------------------
    # INTERNALS
    # ---------------------------------------------------------------

    def _handle_missing(
        self,
        code: str,
        channel: str,
        reason: str | None = None,
        template_id: int | None = None,
    ) -> dict:
        """Build the fallback result and record why the real template was unusable."""
        if reason is None:
            suspended = self.is_suspended(code, channel)
            reason = (
                f"Template '{code}' exists for channel '{channel}' but is "
                "inactive or deleted."
                if suspended
                else f"No active template found for code '{code}', "
                     f"channel '{channel}'."
            )

        logger.error("TemplateResolver: %s Falling back to default copy.", reason)

        context_stub: dict = {}

        if channel == "email":
            fallback = render_fallback_email(
                f"{code.replace('_', ' ').title()} from HMS",
                context_stub,
            )
            result = {
                "found": False,
                "is_fallback": True,
                "code": code,
                "channel": channel,
                "template_id": template_id,
                "version": None,
                "is_system": None,
                "subject": fallback["subject"],
                "html_body": fallback["html_body"],
                "content_html": fallback["content_html"],
                "title": None,
                "message": None,
                "used_variables": fallback["used_variables"],
                "missing_variables": fallback["missing_variables"],
            }
        else:
            fallback = render_fallback_email(
                f"{code.replace('_', ' ').title()}", context_stub
            )
            result = {
                "found": False,
                "is_fallback": True,
                "code": code,
                "channel": channel,
                "template_id": template_id,
                "version": None,
                "is_system": None,
                "subject": None,
                "html_body": None,
                "content_html": None,
                "title": fallback["subject"],
                "message": fallback["content_html"],
                "used_variables": fallback["used_variables"],
                "missing_variables": fallback["missing_variables"],
            }

        result["warnings"] = [reason]
        return result

    @staticmethod
    def _collect_warnings(row, context: dict, result: dict) -> list[str]:
        """Non-fatal problems worth logging on an otherwise successful send."""
        warnings: list[str] = []

        if result.get("missing_variables"):
            warnings.append(
                "Template referenced variables absent from the supplied context: "
                + ", ".join(result["missing_variables"])
            )

        audit = audit_declared_variables(row)
        if audit["undeclared"]:
            warnings.append(
                "Template uses undeclared variables (not listed in `variables`): "
                + ", ".join(audit["undeclared"])
            )

        ## Declared but not supplied by the caller: a likely bug in the caller
        ## rather than the template, but worth surfacing.
        not_supplied = [
            name for name in audit["declared"] if name not in context
        ]
        if not_supplied:
            warnings.append(
                "Declared variables not supplied by the caller: "
                + ", ".join(not_supplied)
            )

        if row.is_email() and not row.subject_template:
            warnings.append("subject_template is empty; subject line will be blank.")

        return warnings

    @staticmethod
    def _log_warnings(result: dict) -> None:
        for warning in result.get("warnings") or []:
            logger.warning(
                "TemplateResolver: [%s/%s] %s",
                result.get("code"), result.get("channel"), warning,
            )

    @staticmethod
    def _empty_result(code: str, channel, warnings: list[str]) -> dict:
        return {
            "found": False,
            "is_fallback": True,
            "code": code,
            "channel": str(channel),
            "template_id": None,
            "version": None,
            "is_system": None,
            "subject": None,
            "html_body": None,
            "content_html": None,
            "title": None,
            "message": None,
            "used_variables": [],
            "missing_variables": [],
            "warnings": warnings,
        }
