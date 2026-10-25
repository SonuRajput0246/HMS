"""Turning the URL a caller arrived on into a tenant.

A workspace is reached at its own subdomain -- `demo1.localhost:4200` -- so the
tenant is a property of the URL, not a field the caller types. The frontend
reads the first DNS label and sends it as `X-Tenant-Slug`; when the backend sits
behind a reverse proxy that terminates the subdomain, the `Host` header carries
it instead and no header is needed.

Whichever way it arrives, the slug is never trusted to select rows on its own:
it is resolved to exactly one tenant, and from that point every query is
confined to that tenant's id by `src/api/tenancy/filters.py`. A caller cannot
reach another tenant's data by inventing a slug, because an unknown slug
resolves to nothing.

Resolution is also what makes the row-writing default in
`src/database/base_model.py` correct: entering the tenant before an insert is
what stamps the new row with it.
"""
import re

from flask import request
from sqlalchemy import select

from src.api.models.tenant_model import Tenant
from src.api.tenancy.context import set_current_tenant_id


def find_tenant_by_slug(db, slug: str | None) -> Tenant | None:
    """The active tenant whose slug is `slug`, or None.

    None covers three cases the callers deliberately do not distinguish -- a
    missing slug, an unknown slug, and a deactivated tenant. Telling an
    anonymous caller which of those it was would hand back exactly the
    account-enumeration oracle the slug was chosen to avoid.
    """
    if not slug or not slug.strip():
        return None
    tenant = (
        db.execute(select(Tenant).filter_by(slug=slug.strip().lower(), is_deleted=False))
        .scalars()
        .first()
    )
    if tenant is None or not tenant.is_active:
        return None
    return tenant


def enter_tenant(db, slug: str | None) -> Tenant | None:
    """Resolve `slug` and make that tenant current for the rest of the request.

    Returns the tenant, or None if it could not be resolved (see above). The
    caller owns the wording of the failure, because "unknown workspace" reads
    differently on the login screen than on a password reset.
    """
    tenant = find_tenant_by_slug(db, slug)
    if tenant is not None:
        set_current_tenant_id(tenant.id)
    return tenant


## The header the frontend sets from the browser's subdomain. Declared here so
## there is exactly one place that knows how a request names its tenant.
TENANT_SLUG_HEADER = "X-Tenant-Slug"

## Host labels that are infrastructure, not a workspace. A request arriving at
## one of these has no tenant -- the correct answer for the bare app domain.
##
## `admin` and `superadmin` are reserved for the platform console itself: if a
## tenant could take one, admin.localhost would resolve as a hotel and the
## management panel would stop being reachable. `is_reserved_slug()` is used on
## the write side so that refusal is decided in one place and cannot drift.
_RESERVED_LABELS = {"localhost", "www", "api", "app", "admin", "superadmin", "sa", "panel"}


def is_reserved_slug(slug: str | None) -> bool:
    """True when `slug` must not be used as a tenant identifier.

    Reserved because it names platform infrastructure rather than a customer
    cafe. Returns True for a missing slug as well: "no slug" is also unusable,
    and callers reject it with the same message.
    """
    if not slug:
        return True
    return slug.strip().lower() in _RESERVED_LABELS


def _slug_from_host(host: str | None) -> str | None:
    """The tenant label at the front of `host`, or None.

    Handles the two shapes this deployment actually sees:

      * `demo1.localhost` -- development, where browsers resolve any
        `*.localhost` name to the loopback interface.
      * `demo1.example.com` -- production, behind a reverse proxy that forwards
        the public host in `X-Forwarded-Host`.

    A bare `example.com` is deliberately NOT read as tenant `example`: with two
    labels there is no way to tell the registrable domain from a subdomain
    without knowing the base domain, and guessing would silently create a
    tenant named after the domain. Only the `*.localhost` case is treated as a
    subdomain at two labels, because there the base is a known constant.
    """
    if not host:
        return None

    ## Proxies chain hosts as "public, internal"; the left-most is the caller's.
    host = host.split(",")[0].strip().lower()
    ## A bracketed IPv6 literal ([::1]) carries no tenant.
    if host.startswith("["):
        return None
    ## Drop the port.
    host = host.split(":", 1)[0]
    if not host or host in _RESERVED_LABELS:
        return None
    ## A bare IPv4 address is infrastructure, not a workspace.
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        return None

    labels = host.split(".")
    if len(labels) < 2:
        return None

    ## Two labels is a subdomain only in development, where the base is the
    ## literal `localhost`.
    if len(labels) == 2 and labels[1] != "localhost":
        return None

    candidate = labels[0]
    if candidate in _RESERVED_LABELS:
        return None
    return candidate


def resolve_tenant_slug_from_request() -> str | None:
    """The tenant slug the current request names, or None.

    The frontend sends `X-Tenant-Slug` derived from the browser's subdomain.
    Falling back to the Host keeps the backend correct when it is put behind a
    reverse proxy that terminates the subdomain and forwards the public host,
    without the frontend needing to send anything.
    """
    header = request.headers.get(TENANT_SLUG_HEADER)
    if header and header.strip():
        return header.strip().lower()

    forwarded = request.headers.get("X-Forwarded-Host")
    return _slug_from_host(forwarded or request.host)


def enter_request_tenant(db) -> Tenant | None:
    """Resolve the current request's tenant and make it current.

    The request-path counterpart to `enter_tenant`. Every unauthenticated
    endpoint that looks a user up by email calls this instead of reading a slug
    from the body, because the tenant is now a property of the URL.
    """
    tenant = find_tenant_by_slug(db, resolve_tenant_slug_from_request())
    if tenant is not None:
        set_current_tenant_id(tenant.id)
    return tenant
