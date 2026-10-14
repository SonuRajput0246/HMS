"""Admin CRUD for the template store.

Distinct from `template_resolver`, which is the read-only send path. This
class backs the Angular screens in src/app/hms/templates and is the only
writer to the `message_templates` table.

GUARANTEES ENFORCED HERE (not in the schema, because they need the database)
----------------------------------------------------------------------------
1. Uniqueness of (code, channel) among live rows -> 409.
   Not a database constraint: MySQL cannot do partial indexes, and a plain
   UNIQUE would also cover soft-deleted rows, making it impossible to
   re-create a template with the same code after deleting it. Note that the
   `postgresql_where=` usage in services_model.py and folio_model.py is
   silently ignored on MySQL and behaves as a plain UNIQUE -- do not copy it.

2. `is_system` rows keep their `code` and `channel`.
   Backend services resolve templates by code, so renaming one would silently
   break the flow it drives.

3. `is_system` rows cannot be deleted.

4. `version` increments on every content change so the UI can show staleness.

5. `deleted_at` is stamped on soft delete and cleared on restore.

RESPONSE SHAPE
--------------
Single-row responses use `service_response` from utils/responses. The list
response returns the `status/data/meta` envelope used by
`admin_service.get_roles`, which the Angular grid expects:

    meta: { current_page, last_page, total_records, per_page }
"""
import logging
from datetime import datetime, timezone

from src.api.models.template_model import Template
from src.api.models.enum_definitions_model import EnumDefinition
from src.api.utils.jwt_helper import get_current_user_id
from src.api.utils.responses import service_response
from src.api.utils.template_codes import default_sort_order
from src.api.utils.template_renderer import (
    audit_declared_variables,
    build_email_html,
    extract_variables,
    render,
    ON_MISSING_KEEP,
)
from src.api.utils.tenant_settings import get_tenant_setting


logger = logging.getLogger(__name__)

## Columns copied from request payload onto the model.
MUTABLE_FIELDS = (
    "code",
    "name",
    "description",
    "subject_template",
    "title_template",
    "message_template",
)

## How much of the subject/title to show in the admin grid.
PREVIEW_LABEL_LENGTH = 90

## `enum_definitions.enum_key` holding the allowed delivery channels.
CHANNEL_ENUM_KEY = "template_channel"

## Channels always accepted, whatever the enum table says. Mirrors the
## resolver: a data edit in the admin UI must not be able to stop an admin
## saving an email template.
CORE_CHANNELS = ("email", "in_app")


class TemplateService:
    """CRUD operations for message templates."""

    def __init__(self, db):
        self.db = db
        self._channel_cache: tuple[str, ...] | None = None


    # ---------------------------------------------------------------
    # READ
    # ---------------------------------------------------------------

    def get_templates(self, data: dict):
        """Paginated list with search and optional channel/status filters."""
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = data.get("search_value")
        channel = data.get("channel")
        is_active = data.get("is_active")

        query = self.db.query(Template).filter(Template.is_deleted == False)

        if search_value:
            val = search_value.strip()
            ## MySQL's utf8mb4_0900_ai_ci collation makes this case-insensitive
            ## without needing LOWER() on both sides.
            query = query.filter(
                Template.code.like(f"{val}%")
                | Template.name.like(f"{val}%")
            )

        if channel:
            ## `Template.channel` is a plain String column, so this must be the
            ## bare value. Passing an enum member here would compile to a
            ## comparison that matches nothing and silently return an empty grid.
            query = query.filter(Template.channel == self._normalise_channel(channel))

        if is_active is not None:
            query = query.filter(Template.is_active == is_active)

        total_records = query.count()

        templates = (
            query
            .order_by(Template.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        template_list = [self._to_list_item(t) for t in templates]
        last_page = (
            (total_records + page_size - 1) // page_size
            if total_records > 0 else 1
        )

        return {
            "status": True,
            "data": template_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size,
            }
        }, 200

    def get_template_by_id(self, template_id):
        """Full detail for the edit form."""
        template = (
            self.db.query(Template)
            .filter_by(is_deleted=False, id=template_id)
            .first()
        )
        if not template:
            return service_response(False, "Template not found", None, 404)

        return service_response(
            True,
            "Template fetched successfully.",
            self._to_detail(template),
            200,
        )

    def get_template_codes(self, data: dict | None = None):
        """Distinct codes, for the Angular code/channel dropdown."""
        channel = (data or {}).get("channel")

        query = self.db.query(Template).filter(Template.is_deleted == False)

        if channel:
            query = query.filter(Template.channel == self._normalise_channel(channel))

        templates = (
            query
            .order_by(Template.sort_order.asc(), Template.code.asc())
            .all()
        )

        codes = []
        seen = set()
        for template in templates:
            if template.code in seen:
                continue
            seen.add(template.code)
            codes.append({"code": template.code, "name": template.name})

        return service_response(True, "Template codes fetched.", codes, 200)


    # ---------------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------------

    def upsert_template(self, data: dict):
        """Create (id=0), update (id>0), or soft-delete (is_deleted=True)."""
        template_id = data.get("id", 0)
        is_deleting = data.get("is_deleted") is True
        now = datetime.now(timezone.utc)
        actor_id = get_current_user_id()

        ## Validated once, up front: both the create and update branches below
        ## persist this value, and the delete path carries whatever channel the
        ## grid row held. Previously an unrecognised value raised a bare
        ## ValueError out of `_to_enum`, which surfaced as a 500.
        normalised_channel = self._normalise_channel(data["channel"])
        if normalised_channel is None:
            return service_response(
                False,
                f"Unknown channel '{data['channel']}'. "
                f"Allowed values: {', '.join(self._valid_channels())}.",
                None,
                400,
            )

        ## ---------- CREATE ----------
        if template_id == 0:
            if is_deleting:
                return service_response(
                    False, "Cannot delete a template that does not exist.", None, 400
                )

            duplicate = self._find_duplicate(data["code"], normalised_channel)
            if duplicate:
                return service_response(
                    False,
                    self._duplicate_message(data["code"], normalised_channel),
                    None,
                    409,
                )

            template = Template(
                is_active=data["is_active"],
                is_deleted=False,
                is_system=False,   ## seeded status is set by the seeder only
                version=1,
                sort_order=self._resolve_sort_order(data),
                variables=self._resolve_variables(data),
                created_by=actor_id,
                updated_by=actor_id,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )

            for field in MUTABLE_FIELDS:
                if field in data:
                    setattr(template, field, data[field])

            template.channel = normalised_channel

            self.db.add(template)
            message = "Template created successfully."
            status_code = 201

        ## ---------- UPDATE ----------
        else:
            template = (
                self.db.query(Template)
                .filter_by(is_deleted=False, id=template_id)
                .first()
            )
            if not template:
                return service_response(False, "Template not found", None, 404)

            ## Guard: seeded templates keep the identity services resolve on.
            if template.is_system:
                identity_conflict = self._identity_conflict(template, data)
                if identity_conflict:
                    return service_response(False, identity_conflict, None, 400)

                ## Guard: seeded templates cannot be deleted.
                if is_deleting:
                    return service_response(
                        False,
                        "This is a system template and cannot be deleted. "
                        "Set it inactive instead to stop it from being used.",
                        None,
                        400,
                    )

            ## Only flag a duplicate if identity actually changes.
            identity_changed = (
                template.code != data["code"]
                or (template.channel or "") != normalised_channel
            )
            if identity_changed:
                duplicate = self._find_duplicate(data["code"], normalised_channel)
                if duplicate:
                    return service_response(
                        False,
                        self._duplicate_message(data["code"], normalised_channel),
                        None,
                        409,
                    )

            for field in MUTABLE_FIELDS:
                if field in data:
                    setattr(template, field, data[field])

            template.channel = normalised_channel

            ## Only overwrite when supplied, so a partial payload cannot wipe it.
            if "variables" in data:
                template.variables = self._resolve_variables(data)

            template.is_active = data["is_active"]
            template.updated_by = actor_id
            template.updated_at = now

            ## An explicit save is a content change, so record a new version.
            ## Diffing against a snapshot would mean threading the pre-update
            ## values through the whole assignment block for no real gain.
            template.version += 1

            message = "Template updated successfully."
            status_code = 200

        ## ---------- SOFT DELETE / RESTORE ----------
        if is_deleting:
            template.is_deleted = True
            template.deleted_at = now
            template.is_active = False
            template.updated_by = actor_id
            template.updated_at = now
            message = "Template deleted successfully."

        ## ---------- VERSION ----------
        ## Already incremented in the update branch above.

        self.db.commit()
        self.db.refresh(template)

        return service_response(True, message, self._to_detail(template), status_code)

    def preview_template(self, data: dict):
        """Render an unsaved draft. Nothing is persisted.

        Missing variables are preserved as literal `{{ token }}` text so the
        author can see what they have not supplied a sample value for, rather
        than staring at a blank gap wondering why.
        """
        ## Nothing is persisted here and the Angular panel calls this on every
        ## keystroke, so an unrecognised channel falls back to email rather than
        ## erroring the way the upsert path does.
        channel = self._normalise_channel(data.get("channel") or "email") or "email"
        context = dict(data.get("sample_context") or {})

        ## Fill gaps from a supplied `variables` map so the preview still has
        ## something to show for tokens the author has not typed a value for.
        for name in (data.get("variables") or []):
            context.setdefault(name, "")

        ## The brand is not a sample value: the server knows the hotel's real
        ## one, so override whatever placeholder the client sent. Without this
        ## the preview footer would show a hardcoded 'HMS' while the real send
        ## brands the mail as the hotel.
        context["company_name"] = get_tenant_setting(self.db, "company_name")

        subject_raw = data.get("subject_template") or ""
        title_raw = data.get("title_template") or ""
        message_raw = data.get("message_template") or ""

        subject_result = render(subject_raw, context, escape_values=False,
                                on_missing=ON_MISSING_KEEP)
        title_result = render(title_raw, context, escape_values=False,
                              on_missing=ON_MISSING_KEEP)
        message_result = render(message_raw, context, escape_values=True,
                                on_missing=ON_MISSING_KEEP)

        used = []
        missing = []
        for result in (subject_result, title_result, message_result):
            for name in result.used_variables:
                if name not in used:
                    used.append(name)
            for name in result.missing_variables:
                if name not in missing:
                    missing.append(name)

        preview = {
            "channel": channel,
            "subject": subject_result.output,
            "title": title_result.output,
            "message": message_result.output,
            "html_body": None,
            "used_variables": used,
            "missing_variables": missing,
            "detected_variables": self._detect_all(message_raw, subject_raw, title_raw),
        }

        ## Email previews get the real layout so the author sees the real result.
        if channel == "email":
            preview["html_body"] = build_email_html(
                subject_result.output,
                message_result.output,
                context.get("company_name"),
            )

        return service_response(True, "Preview generated.", preview, 200)


    # ---------------------------------------------------------------
    # INTERNALS
    # ---------------------------------------------------------------

    def _valid_channels(self) -> tuple[str, ...]:
        """Channels an admin may pick, read once per instance from the enum tables.

        Read from `enum_definitions` / `enum_options` rather than a Python enum
        so a new delivery channel is a data change. Cached because one
        `TemplateService` instance serves every admin request on this process
        and the option list only changes on a re-seed.
        """
        if self._channel_cache is None:
            self._channel_cache = self._load_channels()
        return self._channel_cache

    def _load_channels(self) -> tuple[str, ...]:
        """`enum_options` keys for the template_channel enum definition."""
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
            ## Never let a bad enum table lock an admin out of the editor: fall
            ## back to the core channels and log loudly.
            logger.exception(
                "TemplateService: could not read '%s' options. Falling back to %s.",
                CHANNEL_ENUM_KEY, list(CORE_CHANNELS),
            )
            keys = []

        ## Union, not replacement, so deactivating `email` in the admin UI
        ## cannot stop an admin saving an email template.
        return tuple(dict.fromkeys([*keys, *CORE_CHANNELS]))

    def _normalise_channel(self, channel) -> str | None:
        """Accept a raw string like 'email' / 'in_app' or an enum member.

        Returns the bare value for the String column, or None when the value is
        not one of the options in the enum table.
        """
        if channel is None:
            return None

        text = str(getattr(channel, "value", channel)).strip().lower()
        if not text:
            return None

        return text if text in self._valid_channels() else None

    def _find_duplicate(self, code, channel):
        """An existing live row with the same (code, channel)."""
        return (
            self.db.query(Template)
            .filter(
                Template.is_deleted == False,
                Template.code == code,
                ## `or ""` matters: `== None` compiles to SQL `IS NULL`, which
                ## would match a row with a NULL channel and report a bogus 409.
                Template.channel == (self._normalise_channel(channel) or ""),
            )
            .first()
        )

    @staticmethod
    def _duplicate_message(code, channel):
        return (
            f"A template with code '{code}' and channel "
            f"'{channel}' already exists. Codes must be unique per channel."
        )

    def _identity_conflict(self, template, data):
        """Message when a system template's code or channel is being changed."""
        if template.code != data["code"]:
            return (
                f"'{template.code}' is a system template, so its code cannot be "
                f"changed. Create a new template instead, or deactivate this one."
            )

        if (template.channel or "") != self._normalise_channel(data["channel"]):
            return (
                f"'{template.code}' is a system template, so its channel cannot "
                f"be changed. Create a separate template for the other channel."
            )

        return None

    @staticmethod
    def _resolve_variables(data):
        """Use the supplied list, or derive it from the templates.

        Deriving matters: the Angular variable picker and preview read this
        column, so leaving it NULL for an API-only caller would make those
        controls silently empty.
        """
        supplied = data.get("variables")

        if supplied is None:
            detected = []
            for field in ("subject_template", "title_template", "message_template"):
                for name in extract_variables(data.get(field)):
                    if name not in detected:
                        detected.append(name)
            return detected

        return list(dict.fromkeys(supplied))

    @staticmethod
    def _resolve_sort_order(data):
        """Honour an explicit order, otherwise append to the end."""
        if data.get("sort_order") is not None:
            return int(data["sort_order"])

        supplied_code = data.get("code")
        if not supplied_code:
            return 0

        try:
            return default_sort_order(supplied_code)
        except Exception:
            return 0

    @staticmethod
    def _detect_all(*fields):
        """Every distinct placeholder across several template fields."""
        found = []
        for text in fields:
            for name in extract_variables(text):
                if name not in found:
                    found.append(name)
        return found

    @staticmethod
    def _to_list_item(template) -> dict:
        """Row shape for the admin grid. Omits the full body to keep it light."""
        return {
            "id": template.id,
            "code": template.code,
            "name": template.name,
            "description": template.description,
            "channel": template.channel,
            "is_active": template.is_active,
            "is_system": template.is_system,
            "version": template.version,
            "sort_order": template.sort_order,
            "variables": template.variables or [],
            "preview_label": TemplateService._preview_label(template),
            "has_subject": bool(template.subject_template),
            "has_title": bool(template.title_template),
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "updated_by_name": (
                f"{template.updated_by_user.first_name} {template.updated_by_user.last_name}"
                if template.updated_by_user else None
            ),
        }

    @staticmethod
    def _to_detail(template) -> dict:
        """Full shape for the edit form."""
        return {
            "id": template.id,
            "code": template.code,
            "name": template.name,
            "description": template.description,
            "channel": template.channel,
            "subject_template": template.subject_template,
            "title_template": template.title_template,
            "message_template": template.message_template,
            "variables": template.variables or [],
            "sample_context": template.sample_context or {},
            "is_active": template.is_active,
            "is_system": template.is_system,
            "version": template.version,
            "sort_order": template.sort_order,
            "is_deleted": template.is_deleted,
            "deleted_at": template.deleted_at.isoformat() if template.deleted_at else None,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "created_by": template.created_by,
            "updated_by": template.updated_by,
            "created_by_name": (
                f"{template.created_by_user.first_name} {template.created_by_user.last_name}"
                if template.created_by_user else None
            ),
            "updated_by_name": (
                f"{template.updated_by_user.first_name} {template.updated_by_user.last_name}"
                if template.updated_by_user else None
            ),
            "variable_audit": audit_declared_variables(template),
        }

    @staticmethod
    def _preview_label(template) -> str:
        """Short single-line label for the grid."""
        raw = (
            template.subject_template
            if (template.channel or "") == "email"
            else template.title_template
        ) or template.message_template or ""

        collapsed = " ".join(raw.split())
        if len(collapsed) <= PREVIEW_LABEL_LENGTH:
            return collapsed

        return collapsed[: PREVIEW_LABEL_LENGTH].rstrip() + "..."