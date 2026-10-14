"""Safe renderer for admin-authored message templates.

WHY THIS EXISTS
---------------
Template bodies now live in the database and are editable from the Angular
admin UI. That makes them untrusted input, so they must NOT be handed to a
full template engine. Jinja2 would expose attribute traversal
(`{{ user.__class__ }}`) and, without a sandbox, arbitrary code execution.

This module deliberately does only one thing: substitute `{{ variable }}`
tokens with values from a fixed context dict.

    - The token pattern only matches bare identifiers
      ([A-Za-z_][A-Za-z0-9_]*). Anything else -- `{{ a.b }}`, `{{ 1+1 }}`,
      `{% for %}` -- is left in the output untouched so the mistake stays
      visible instead of silently disappearing.
    - There is no expression evaluation, no attribute access, no function
      calling, no imports. A template cannot do anything except substitute
      text you already supplied.
    - Values are HTML-escaped by default, so a placeholder inside the email
      HTML fragment cannot inject markup even if the context value is
      attacker-influenced.
    - A missing key never raises. It renders empty and is reported back via
      `RenderResult.missing_variables` so the CRUD API and the logs can flag it.

SYNTAX
------
    {{ user_name }}   {{user_name}}   {{   user_name   }}

FAIL-SAFE CALLERS
-----------------
Callers on the auth path should not call these functions directly. Use
`TemplateResolver.render()` in src/api/services/template_resolver.py, which
resolves the row, catches render failures, and substitutes
`render_fallback_email` copy so a bad template cannot break a login, an
activation, or a password reset.
"""
import html
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable


## Only bare identifiers are recognised as placeholders. Dots, spaces, digits
## at the start, and any Jinja/strftime syntax are deliberately NOT matched, so
## they pass through literally and stay visible to the author.
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

## Layout file that wraps an email fragment. The only remaining static template.
LAYOUT_RELATIVE_PATH = os.path.join("templates", "emails", "layout.html")

## Fallback copy used when a template row is missing, inactive, or fails to
## render. A send must degrade rather than break the auth flow.
FALLBACK_MESSAGE = (
    "<p>Hello {{ user_name }},</p>"
    "<p>A notification was generated for your account but the message "
    "template could not be loaded. Please contact support if this persists.</p>"
    "<p>Regards,<br><b>{{ company_name }}</b></p>"
)

## Printed only when a caller passes no brand at all. The real value comes from
## the current tenant's `system_settings` and reaches the renderer through the
## render context; this is a rendering-layer last resort, not the data default.
FALLBACK_COMPANY_NAME = "HMS"

ON_MISSING_EMPTY = "empty"
ON_MISSING_KEEP = "keep"


@dataclass
class RenderResult:
    """Outcome of a single render pass.

    `output` is the final string. The variable lists exist so the CRUD API can
    validate what an admin typed and so send failures can be logged precisely.
    """

    output: str
    used_variables: list[str] = field(default_factory=list)
    missing_variables: list[str] = field(default_factory=list)

    @property
    def has_missing(self) -> bool:
        return bool(self.missing_variables)


def extract_variables(text: str | None) -> list[str]:
    """Every distinct placeholder name appearing in `text`, in first-seen order.

    Used by the CRUD API to cross-check the `variables` column against the
    tokens actually present in the template body.
    """
    if not text:
        return []
    seen: list[str] = []
    for name in PLACEHOLDER_PATTERN.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


def render(
    text: str | None,
    context: dict | None = None,
    escape_values: bool = True,
    on_missing: str = ON_MISSING_EMPTY,
) -> RenderResult:
    """Substitute `{{ variable }}` tokens in `text` from `context`.

    Args:
        text: The template string. May be None (treated as empty).
        context: Values to substitute. Keys not present here are "missing".
        escape_values: True for HTML targets (message bodies). False for plain
            text targets (subject and in-app title), where escaping would
            corrupt the output.
        on_missing: ON_MISSING_EMPTY renders a missing key as an empty string
            (correct for production sends). ON_MISSING_KEEP leaves the literal
            `{{ key }}` in place, which is what the preview endpoint uses so an
            author can see what they forgot to supply.
    """
    if not text:
        return RenderResult(output="")

    values = context or {}
    used: list[str] = []
    missing: list[str] = []

    def substitute(match: "re.Match") -> str:
        name = match.group(1)

        if name not in values:
            if name not in missing:
                missing.append(name)
            return match.group(0) if on_missing == ON_MISSING_KEEP else ""

        value = values[name]
        ## None and empty values are treated as present-but-blank so a caller
        ## can deliberately clear a field without it counting as an error.
        text_value = "" if value is None else str(value)

        if escape_values:
            text_value = html.escape(text_value, quote=True)

        if name not in used:
            used.append(name)
        return text_value

    return RenderResult(
        output=PLACEHOLDER_PATTERN.sub(substitute, text),
        used_variables=used,
        missing_variables=missing,
    )


def _project_root() -> str:
    """HMS_Flask package root, derived from this file's location."""
    ## src/api/utils/template_renderer.py -> up 4 -> HMS_Flask/
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
    )


@lru_cache(maxsize=1)
def load_layout() -> str:
    """Read the static email layout once and cache it.

    Deliberately uses plain file IO rather than Flask's `render_template` so
    rendering works outside an application context (seeders, CLI, background
    workers) and so there is exactly one rendering code path in this project.
    """
    path = os.path.join(_project_root(), LAYOUT_RELATIVE_PATH)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def build_email_html(
    subject: str | None,
    content_fragment: str,
    company_name: str | None = None,
) -> str:
    """Wrap a rendered HTML fragment in the static email layout.

    `subject` and `content_fragment` are expected to be already escaped:
    `subject` and `company_name` are escaped here, and the fragment is escaped
    at the point its own placeholders were substituted. All three are then
    inserted with escaping off so the values are not double-escaped.

    `company_name` is the current hotel's brand; when omitted the generic
    fallback is used, so a caller that has no tenant context still renders.
    """
    safe_subject = html.escape(subject or "", quote=True)
    safe_company = html.escape(company_name or FALLBACK_COMPANY_NAME, quote=True)
    result = render(
        load_layout(),
        {
            "subject": safe_subject,
            "content": content_fragment,
            ## The hotel's own brand, so a multi-tenant install does not send
            ## every hotel's mail under the product's name.
            "company_name": safe_company,
            ## Footer copyright year. Plain integer, safe either way.
            "year": datetime.now(timezone.utc).year,
        },
        escape_values=False,
    )
    return result.output


def render_subject(template_row, context: dict, on_missing: str = ON_MISSING_EMPTY) -> RenderResult:
    """Render `subject_template`. Plain text, so values are NOT escaped."""
    return render(
        getattr(template_row, "subject_template", None),
        context,
        escape_values=False,
        on_missing=on_missing,
    )


def render_title(template_row, context: dict, on_missing: str = ON_MISSING_EMPTY) -> RenderResult:
    """Render `title_template`. Plain text, so values are NOT escaped."""
    return render(
        getattr(template_row, "title_template", None),
        context,
        escape_values=False,
        on_missing=on_missing,
    )


def render_message(template_row, context: dict, on_missing: str = ON_MISSING_EMPTY) -> RenderResult:
    """Render `message_template` as an HTML fragment with escaped values."""
    return render(
        getattr(template_row, "message_template", None),
        context,
        escape_values=True,
        on_missing=on_missing,
    )


def render_email(template_row, context: dict) -> dict:
    """Full render for `channel='email'`.

    Returns:
        {
            "subject": str,
            "html_body": str,          # fragment wrapped in the static layout
            "content_html": str,       # fragment on its own
            "used_variables": list[str],
            "missing_variables": list[str],
        }
    """
    subject_result = render_subject(template_row, context)
    message_result = render_message(template_row, context)

    return {
        "subject": subject_result.output,
        "html_body": build_email_html(
            subject_result.output,
            message_result.output,
            (context or {}).get("company_name"),
        ),
        "content_html": message_result.output,
        "used_variables": _merge_unique(
            subject_result.used_variables, message_result.used_variables
        ),
        "missing_variables": _merge_unique(
            subject_result.missing_variables, message_result.missing_variables
        ),
    }


def render_in_app(template_row, context: dict) -> dict:
    """Full render for `channel='in_app'`.

    The message body is authored as HTML too, so that a template can be moved
    between channels and the escaping rule stays identical. The Angular client
    decides whether to render it as markup or strip it.
    """
    title_result = render_title(template_row, context)
    message_result = render_message(template_row, context)

    return {
        "title": title_result.output,
        "message": message_result.output,
        "used_variables": _merge_unique(
            title_result.used_variables, message_result.used_variables
        ),
        "missing_variables": _merge_unique(
            title_result.missing_variables, message_result.missing_variables
        ),
    }


def render_fallback_email(subject: str, context: dict) -> dict:
    """Last-resort email used when a stored template is unusable.

    Guarantees `email_service` can still deliver a meaningful message instead
    of raising and breaking a login or password-reset request.
    """
    subject_result = render(subject, context, escape_values=False)
    message_result = render(FALLBACK_MESSAGE, context, escape_values=True)
    return {
        "subject": subject_result.output,
        "html_body": build_email_html(
            subject_result.output,
            message_result.output,
            (context or {}).get("company_name"),
        ),
        "content_html": message_result.output,
        "used_variables": _merge_unique(
            subject_result.used_variables, message_result.used_variables
        ),
        "missing_variables": _merge_unique(
            subject_result.missing_variables, message_result.missing_variables
        ),
        "is_fallback": True,
    }


def audit_declared_variables(template_row) -> dict:
    """Compare the `variables` column against tokens actually used.

    Called by the CRUD API so an author is told about a placeholder that is
    referenced but not declared (or declared but never used).
    """
    declared: Iterable[str] = getattr(template_row, "variables", None) or []
    declared = [str(item) for item in declared]

    used = extract_variables(getattr(template_row, "subject_template", None))
    used += extract_variables(getattr(template_row, "title_template", None))
    used += extract_variables(getattr(template_row, "message_template", None))

    undeclared = [name for name in dict.fromkeys(used) if name not in declared]
    unused = [name for name in declared if name not in used]

    return {
        "declared": declared,
        "used": list(dict.fromkeys(used)),
        "undeclared": undeclared,
        "unused": unused,
    }


def _merge_unique(*groups: list[str]) -> list[str]:
    """Concatenate lists preserving order and dropping duplicates."""
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in merged:
                merged.append(item)
    return merged