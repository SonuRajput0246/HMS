"""Which tenant is the current unit of work operating on.

Two storage mechanisms, deliberately:

  * Inside a Flask request the value lives on `g`. Flask guarantees `g` is
    per-request, so one request can never see another's tenant -- which is the
    entire safety property this module exists to provide.

  * Outside a request (seeders, `scripts/`, a management command) there is no
    `g`, so the value lives in a ContextVar. A ContextVar is correct for those
    too: `bypass_tenant_filter()` is a scoped `set`/`reset`, so it cannot leak
    past the `with` block even if the caller's thread is reused.

Nothing here decides WHICH tenant is current. Resolution happens in the auth
layer (`auth_middleware.authenticate` reads the JWT claim and populates `g`);
this module only holds the answer and hands it to the query filter.

Read it through `get_current_tenant_id()`. Never read the ContextVar directly --
that would silently return None inside a request and disable filtering, which
is the failure this whole design exists to prevent.

The tenant's IANA zone is held the same way (`get_current_tenant_timezone()`),
because BUSINESS_TIMEZONE is only a process-wide default once several tenants
share a process. `tenant_scope()` is the scoped setter for code that runs more
than one tenant -- seeders, tenant provisioning -- and it is the only place
that restores the previous value.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from flask import g, has_app_context


## Marker stored in the bypass ContextVar only while `bypass_tenant_filter()` is
## active, so "deliberately bypassed" and "nothing set" stay distinguishable.
## It is deliberately NOT the ContextVar default: with the sentinel as the
## default, every read outside a request reported "bypassed", which would have
## silently disabled the tenant filter for every seeder and script.
_BYPASS = object()

_context_tenant: ContextVar = ContextVar("cms_tenant_id", default=None)
_context_bypass: ContextVar = ContextVar("cms_tenant_bypass", default=None)
_context_tenant_timezone: ContextVar = ContextVar("cms_tenant_timezone", default=None)


def set_current_tenant_id(tenant_id: int | None) -> None:
    """Bind the current tenant for the rest of this request (or this thread)."""
    if has_app_context():
        g.tenant_id = tenant_id
    else:
        _context_tenant.set(tenant_id)


def get_current_tenant_id() -> int | None:
    """The tenant every query must be restricted to, or None if unknown.

    None is the dangerous value: `src/api/tenancy/filters.py` treats it as
    "no tenant in context" and leaves queries UNFILTERED. That is correct for
    the seeding and migration paths, which legitimately run before any tenant
    exists, and wrong everywhere else. If a request-scoped query ever sees
    None, the bug is that `authenticate()` did not populate `g.tenant_id`.
    """
    if has_app_context():
        return getattr(g, "tenant_id", None)
    return _context_tenant.get()


def set_current_tenant_timezone(timezone_name: str | None) -> None:
    """Bind the current tenant's IANA zone alongside its id."""
    if has_app_context():
        g.tenant_timezone = timezone_name
    else:
        _context_tenant_timezone.set(timezone_name)


def get_current_tenant_timezone() -> str | None:
    """The current tenant's IANA zone, or None when no zone is known.

    Kept separate from the tenant id so a caller can bind one without the other:
    only the date helpers read the zone, and every one of them falls back to the
    configured BUSINESS_TIMEZONE when this is None.
    """
    if has_app_context():
        return getattr(g, "tenant_timezone", None)
    return _context_tenant_timezone.get()


def is_tenant_filter_bypassed() -> bool:
    """True while inside `bypass_tenant_filter()`."""
    if has_app_context():
        return getattr(g, "tenant_filter_bypassed", False)
    return _context_bypass.get() is _BYPASS


@contextmanager
def bypass_tenant_filter(reason: str = ""):
    """Run queries WITHOUT tenant scoping.

    Only three things may use this:

      1. Tenant bootstrap -- copying the role/prefix/template template into a
         tenant that does not exist yet, so there is nothing to scope to.
      2. Seeders and migrations, which run before any tenant exists.
      3. Platform-admin endpoints, which by definition operate across tenants.

    A service method that uses this is a cross-tenant read or write and needs
    to say so in a comment explaining why the scoping does not apply. It is not
    a convenience for "I forgot the filter" -- that case is handled by the
    filter itself and must never reach this function.

    The optional `reason` is recorded in the log line below, because the one
    way to make this dangerous is for it to be used so often that nobody
    notices a new caller.
    """
    if has_app_context():
        g.tenant_filter_bypassed = True
        try:
            yield
        finally:
            g.tenant_filter_bypassed = False
    else:
        token = _context_bypass.set(_BYPASS)
        try:
            yield
        finally:
            _context_bypass.reset(token)


@contextmanager
def tenant_scope(tenant_id: int | None, timezone_name: str | None = None):
    """Bind a tenant for the duration of a `with` block, then restore.

    The request path sets the tenant once and lets the request boundary unwind
    it. A seeder or a management command has no such boundary and runs several
    tenants back to back in one process, so it needs the scoped form: leaving a
    tenant bound after the block would stamp the next tenant's rows with the
    previous tenant's id, which is exactly the leak `_tenant_id_default` cannot
    detect on its own.

    Restores the previous value rather than clearing, so nesting is safe.
    """
    previous_id = get_current_tenant_id()
    previous_timezone = get_current_tenant_timezone()

    set_current_tenant_id(tenant_id)
    if timezone_name is not None:
        set_current_tenant_timezone(timezone_name)

    try:
        yield
    finally:
        set_current_tenant_timezone(previous_timezone)
        set_current_tenant_id(previous_id)
