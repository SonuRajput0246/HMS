"""Request validation for the template CRUD API.

Handles three things that plain field types cannot:

1. CHANNEL-CONDITIONAL FIELDS. `subject_template` is mandatory for
   channel='email' and irrelevant for channel='in_app'; `title_template` is
   the mirror image. Enforced in `_validate_channel_fields`.

2. DECLARED-VS-USED PLACEHOLDERS. `message_template` and friends are parsed
   for `{{ variable }}` tokens and cross-checked against the `variables` list
   so the admin UI's variable picker and preview cannot drift from the body.
   Enforced in `_validate_variables`.

3. WHITESPACE-ONLY OPTIONAL TEXT. `BaseSchema.normalize_strings` rejects any
   blank string unless the field name is in `OPTIONAL_FIELDS`. Without the
   extension below, an `in_app` row whose client sends `subject_template: ""`
   would be rejected with a confusing "cannot be empty or only spaces".

Marshmallow 4 note: `fields.missing` no longer exists. Do not introduce it.
"""
from src.api.schemas.common.base import BaseSchema
from src.api.utils.template_renderer import extract_variables
from src.api.schemas.common.id_schema import id_schema_factory
from src.api.utils.template_codes import all_codes, is_known_code
from src.api.schemas.common.pagination_schema import PaginationSchema
from marshmallow import fields, validate, validates_schema, ValidationError


## Single source of truth for valid channel values: 'email' and 'in_app'
CHANNEL_VALUES = ["email", "in_app"]

## How many single-character edits still count as "probably a typo".
## 1 catches trailing/duplicated characters, 2 catches a swapped pair.
_TYPO_TOLERANCE = 2

## Uppercase snake identifiers. Anchored because validate.Regexp uses re.match.
CODE_REGEX = r"^[A-Z][A-Z0-9_]*$"

## Upper bound on how much HTML a single message body may carry.
MESSAGE_MAX_LENGTH = 20000


## ---------------------------------------------------------------------------
## READ SCHEMAS
## ---------------------------------------------------------------------------

class GetTemplatesSchema(PaginationSchema):
    """List filter. Inherits page_number / page_size / search_value."""

    channel = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(
            CHANNEL_VALUES,
            error="Channel must be either 'email' or 'in_app'.",
        ),
    )

    is_active = fields.Boolean(
        required=False,
        allow_none=True,
    )


GetTemplateByIdSchema = id_schema_factory("id", "Template Id")


class GetTemplateCodesSchema(BaseSchema):
    """Filter for the code/channel dropdown."""

    channel = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(
            CHANNEL_VALUES,
            error="Channel must be either 'email' or 'in_app'.",
        ),
    )


## ---------------------------------------------------------------------------
## UPSERT SCHEMA
## ---------------------------------------------------------------------------

_UpsertTemplateIdSchema = id_schema_factory(
    "id",
    "Template Id",
    min_value=0,
    required=True,
)


class UpsertTemplateSchema(_UpsertTemplateIdSchema):
    """Create (id=0) or update (id>0) a template.

    `is_deleted=True` performs the soft delete, matching the convention used by
    `upsert_role` in admin_service.py, which the Angular delete button calls.
    """

    ## Extends the base tuple so a blank subject on an in_app row, or a blank
    ## title on an email row, becomes None instead of a validation error.
    OPTIONAL_FIELDS = BaseSchema.OPTIONAL_FIELDS + (
        "description",
        "subject_template",
        "title_template",
        "variables",
        "sample_context",
    )

    code = fields.String(
        required=True,
        allow_none=False,
        validate=[
            validate.Regexp(
                CODE_REGEX,
                error=(
                    "Code must be uppercase letters, digits and underscores, "
                    "and must not start with a digit (e.g. PASSWORD_RESET_OTP)."
                ),
            ),
            validate.Length(
                min=2, max=100, error="Code must be between 2 and 100 characters."
            ),
        ],
    )

    name = fields.String(
        required=True,
        allow_none=False,
        validate=validate.Length(
            min=1, max=150, error="Name must be between 1 and 150 characters."
        ),
    )

    description = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(
            max=500, error="Description cannot exceed 500 characters."
        ),
    )

    channel = fields.String(
        required=True,
        allow_none=False,
        validate=validate.OneOf(
            CHANNEL_VALUES,
            error="Channel must be either 'email' or 'in_app'.",
        ),
    )

    subject_template = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(
            max=500, error="Subject template cannot exceed 500 characters."
        ),
    )

    title_template = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(
            max=255, error="Title template cannot exceed 255 characters."
        ),
    )

    ## Field-level `required` is False because a soft delete carries no template
    ## content; presence is enforced in `_validate_content_fields` below.
    message_template = fields.String(
        required=False,
        allow_none=False,
        validate=validate.Length(
            max=MESSAGE_MAX_LENGTH,
            error=(
                "Message template cannot exceed "
                f"{MESSAGE_MAX_LENGTH} characters."
            ),
        ),
    )

    variables = fields.List(
        fields.String(validate=validate.Length(min=1, max=64)),
        required=False,
        allow_none=True,
    )

    sample_context = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=False,
        allow_none=True,
    )

    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)

    @validates_schema
    def _validate_content_fields(self, data, **kwargs):
        """`message_template` must be present unless this is a soft delete."""
        if data.get("is_deleted") is True:
            return

        if not _is_present(data.get("message_template")):
            raise ValidationError({
                "message_template": ["Message template is required."]
            })

    @validates_schema
    def _validate_channel_fields(self, data, **kwargs):
        """Require the field that belongs to the chosen channel.

        Skipped entirely for a soft delete. The Angular list deletes through
        the same upsert endpoint using a minimal payload built from the grid
        row, which deliberately omits the body fields -- so requiring a
        subject or title on delete would make in_app rows undeletable.
        """
        if data.get("is_deleted") is True:
            return

        channel = data.get("channel")
        if not channel:
            return

        errors = {}

        if channel == "email":
            if not _is_present(data.get("subject_template")):
                errors["subject_template"] = [
                    "Subject template is required when channel is 'email'."
                ]
            if data.get("title_template"):
                ## Harmless, but it would render an unused column value.
                ## Left as an error so the stored row stays unambiguous.
                errors["title_template"] = [
                    "Title template applies to channel 'in_app' only. Leave it empty "
                    "for an email template."
                ]

        elif channel == "in_app":
            if not _is_present(data.get("title_template")):
                errors["title_template"] = [
                    "Title template is required when channel is 'in_app'."
                ]
            if data.get("subject_template"):
                errors["subject_template"] = [
                    "Subject template applies to channel 'email' only. Leave it empty "
                    "for an in_app template."
                ]

        if errors:
            raise ValidationError(errors)

    @validates_schema
    def _validate_variables(self, data, **kwargs):
        """Cross-check declared variables against tokens in the templates.

        Only enforced when `variables` is supplied. When it is omitted the CRUD
        service derives it from the templates, so an API-only caller is not
        forced to duplicate the parser.

        Skipped for a soft delete, which carries no template content.
        """
        if data.get("is_deleted") is True:
            return

        declared = data.get("variables")

        if declared is None:
            return

        ## De-duplicate while preserving order.
        declared = list(dict.fromkeys(declared))

        used = []
        for field_name in (
            "subject_template",
            "title_template",
            "message_template",
        ):
            for name in extract_variables(data.get(field_name)):
                if name not in used:
                    used.append(name)

        undeclared = [name for name in used if name not in declared]
        if undeclared:
            raise ValidationError({
                "variables": [
                    "Declared variables do not cover every placeholder used in the "
                    "templates. Missing: " + ", ".join(undeclared)
                ]
            })

        ## A sample value for a placeholder that does not exist is always a typo.
        sample_keys = set((data.get("sample_context") or {}).keys())
        stray = sorted(sample_keys - set(declared))
        if stray:
            raise ValidationError({
                "sample_context": [
                    "Sample values are provided for variables that are not "
                    "declared: " + ", ".join(stray)
                ]
            })

    @validates_schema
    def _validate_code_known_or_custom(self, data, **kwargs):
        """Block near-miss spellings of a shipped code.

        A typo like `PASSWORD_RESET_OTPP` would create a row that no service
        ever reads: the template silently never sends, and the admin believes
        the flow is configured. Near-miss detection catches that, which a plain
        "is this a known code" check cannot, because the typo is by definition
        unknown.

        Genuinely new codes (`WELCOME_NOTIFICATION`, `RESERVATION_CONFIRMED`)
        stay allowed, since they are nowhere near a shipped code.
        """
        code = data.get("code")
        if not code:
            return

        if is_known_code(code):
            return

        normalised = _normalise_for_similarity(code)

        for known in all_codes():
            known_normalised = _normalise_for_similarity(known)
            distance = _levenshtein(normalised, known_normalised)

            if distance == 0:
                raise ValidationError({
                    "code": [
                        f"'{code}' is the same as the system code '{known}' when "
                        "underscores are ignored. Use the system code as-is."
                    ]
                })

            if distance <= _TYPO_TOLERANCE:
                raise ValidationError({
                    "code": [
                        f"'{code}' is very close to the system code '{known}', which "
                        "is probably a typo. Correct the spelling, or choose a name "
                        "that is clearly distinct."
                    ]
                })


## ---------------------------------------------------------------------------
## PREVIEW SCHEMA
## ---------------------------------------------------------------------------

class PreviewTemplateSchema(BaseSchema):
    """Render an unsaved draft against sample values.

    Used by the Angular live-preview panel. `code`, `name`, `is_active`, and
    `is_deleted` are deliberately absent: nothing is persisted, so identity and
    audit fields are irrelevant here.
    """

    OPTIONAL_FIELDS = BaseSchema.OPTIONAL_FIELDS + (
        "subject_template",
        "title_template",
    )

    channel = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(
            CHANNEL_VALUES,
            error="Channel must be either 'email' or 'in_app'.",
        ),
    )

    subject_template = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(max=500),
    )

    title_template = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(max=255),
    )

    message_template = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(max=MESSAGE_MAX_LENGTH),
    )

    ## Caller-supplied values override any stored sample_context.
    sample_context = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=False,
        allow_none=True,
    )

    variables = fields.List(
        fields.String(),
        required=False,
        allow_none=True,
    )


def _is_present(value) -> bool:
    """True for a non-empty, non-whitespace string."""
    return isinstance(value, str) and value.strip() != ""


def _normalise_for_similarity(code: str) -> str:
    """Collapse a code to bare uppercase letters so formatting is ignored.

    This is what makes `EMAILVERIFICATION_OTP` and `Email_Verification_Otp`
    comparable, and what lets `_levenshtein` measure the actual spelling rather
    than underscore placement.
    """
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _levenshtein(left: str, right: str) -> int:
    """Standard edit distance via a single rolling row.

    Inputs here are short identifiers, so the O(n*m) cost is irrelevant and the
    straightforward two-row implementation is clearer than any optimisation.
    """
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))

    for i, left_ch in enumerate(left, start=1):
        current = [i]
        for j, right_ch in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_ch != right_ch)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current

    return previous[-1]