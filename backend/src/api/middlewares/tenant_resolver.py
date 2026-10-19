"""Resolve which tenant a request is about, before anything reads the database.

Every tenant-scoped table is filtered by the tenant in the request context (see
src/database/tenant_context.py). That context therefore has to be established
before `authenticate()` runs: `users` is tenant-scoped, so even looking up the
caller needs the tenant to be known already. This is the only place that decides
it.

Resolution order:

  1. The **X-Tenant header**. This is what the frontend sends, because in
     development the API sits on a different origin than the app, so the API
     never sees the tenant subdomain in its own Host header. It is also what
     makes two tenants drivable side by side in one browser.
  2. The **subdomain of Host**. This is the production path, where the app and
     the API are both behind acme.hms.example.com.

If both are present they must agree, so a misconfigured proxy is a loud 400
rather than a request silently served from the wrong hotel.

Resolution decides which tenant a request is *about*; it never grants access by
itself. A caller can name any tenant in the header and will receive that
tenant's public data -- its login page, its sliders -- and nothing else, because
the JWT's tenant claim is cross-checked against this in the auth layer. Getting
`g.tenant_id` from a header is safe precisely because it is not an
authorization decision.
"""
from flask import current_app, g, request

from src.api.services.tenant_service import TenantService
from src.api.utils.errors import BadRequestError, ForbiddenError, ResourceNotFoundError
from src.database.session import db_session
from src.database.tenant_context import clear_tenant_context, set_tenant_context


## Paths that must never resolve a tenant.
##
## Platform routes administer tenants *from above*, so requiring a tenant would
## make them unreachable -- there is no tenant to name. Anything added here is a
## deliberate statement that the route sits outside tenancy, and the list is
## short and explicit for exactly that reason.
TENANT_EXEMPT_PREFIXES = ("/api/v1/platform", "/static")


## Host labels the platform keeps for itself. A hotel is addressed by a
## subdomain, so a slug that collides with one of these would either shadow the
## platform console or shadow the API that serves it. Enforced at creation time
## by the platform console rather than at resolve time, so the refusal happens
## where an operator can act on it.
RESERVED_SLUGS: frozenset[str] = frozenset({
    "localhost",
    "www",
    "api",
    "app",
    "admin",
    "platform",
    "superadmin",
    "super-admin",
    "sa",
    "panel",
    "console",
})


def is_reserved_slug(slug: str | None) -> bool:
    """Is this slug claimed by the platform rather than a hotel?

    Case- and whitespace-insensitive, because the comparison happens against
    whatever an operator typed into a form, not against a normalised value.
    """
    if not slug:
        return False
    return slug.strip().lower() in RESERVED_SLUGS


def _host_slug() -> str | None:
    """The leading label of the Host header, when the host is a tenant host.

    Returns None for a host that carries no tenant -- the bare domain, an IP, or
    localhost -- because "no tenant named" is a legitimate state, not an error.
    """
    host = (request.host or "").split(":", 1)[0].strip().lower()
    if not host:
        return None

    ## Bare hosts carry no tenant.
    if host in ("localhost", "127.0.0.1", "::1"):
        return None

    base_domain = (current_app.config.get("TENANT_BASE_DOMAIN") or "").strip().lower()

    if base_domain and host.endswith("." + base_domain):
        prefix = host[: -(len(base_domain) + 1)]
        return prefix.split(".")[0] or None

    ## <tenant>.localhost is the documented local-development host. Browsers
    ## resolve *.localhost to loopback without a hosts-file entry (RFC 6761), so
    ## supporting it costs nothing and removes a setup step.
    if host.endswith(".localhost"):
        return host[: -len(".localhost")].split(".")[0] or None

    ## Any other host is not a tenant host. Returning None rather than guessing
    ## a label keeps a stray Host header from selecting an arbitrary tenant.
    return None


def _header_slug() -> str | None:
    header_name = current_app.config.get("TENANT_HEADER_NAME", "X-Tenant")
    value = (request.headers.get(header_name) or "").strip().lower()
    return value or None


def resolve_tenant():
    """Resolve the tenant for the current request onto flask.g.

    Raises when the request names no tenant, or names one that is unusable
    (unknown, or deactivated). The caller runs this only for routes that belong
    to a hotel -- see init_tenant_resolver and TENANT_EXEMPT_PREFIXES.

    An archived tenant never reaches here: `TenantService.find_by_slug` filters
    `is_deleted`, so it reads as unknown rather than as a third kind of
    unusable hotel.
    """
    clear_tenant_context()
    g.tenant = None
    g.tenant_id = None

    host_slug = _host_slug()
    header_slug = _header_slug()

    if host_slug and header_slug and host_slug != header_slug:
        raise BadRequestError(
            f"Conflicting tenant: host says '{host_slug}', "
            f"{current_app.config.get('TENANT_HEADER_NAME', 'X-Tenant')} "
            f"header says '{header_slug}'."
        )

    slug = header_slug or host_slug
    if not slug:
        ## Every route this hook covers belongs to a hotel, so a request that
        ## names none is refused rather than served unscoped. Letting it through
        ## as "no tenant" would run the request with no tenant filter at all --
        ## an unscoped `users` lookup on the login route, for instance, could
        ## match a row from any hotel. Platform routes, which sit above tenants,
        ## are excluded by TENANT_EXEMPT_PREFIXES before this is reached.
        raise ResourceNotFoundError("No hotel is associated with this request.")

    tenant = TenantService(db_session).find_by_slug(slug)
    if tenant is None:
        raise ResourceNotFoundError(f"Unknown tenant '{slug}'.")

    if not tenant.is_active:
        raise ForbiddenError("This account is not active.")

    g.tenant = tenant
    g.tenant_id = tenant.id
    set_tenant_context(tenant.id)

    return None


def init_tenant_resolver(app):
    """Register tenant resolution on the app.

    One app-wide before_request rather than a per-blueprint hook: the tenant
    applies to every blueprint, and a single list of exemptions is far easier to
    audit than a per-module convention that a new blueprint can forget.
    """

    @app.before_request
    def _resolve_tenant():
        ## A CORS preflight carries no Authorization header and no tenant
        ## knowledge. Refusing it would break every cross-origin call before it
        ## was ever made.
        if request.method == "OPTIONS":
            return None

        path = request.path or ""
        if path.startswith(TENANT_EXEMPT_PREFIXES):
            return None

        return resolve_tenant()
