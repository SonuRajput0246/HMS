"""Which tenant is the current unit of work about?

Held in a ContextVar rather than on flask.g because not every unit of work is a
request. Provisioning a tenant, seeding, and the platform routes all touch
tenant-scoped tables with no HTTP request in sight, and they need to say which
tenant they mean just as clearly as a request does.

Two states, and the distinction matters:

  * a tenant id   -- "this unit of work is about this hotel"
  * None          -- "this unit of work is explicitly outside tenancy"

`None` is not a fallback for "nobody said". Code that means to work across
tenants has to say so with bypass_tenant_filter(), which is greppable. When the
enforcement layer lands, an insert into a tenant-scoped table with no context is
a programming error and will be refused rather than silently defaulted.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_current_tenant_id: ContextVar[int | None] = ContextVar("current_tenant_id", default=None)


def current_tenant_id() -> int | None:
    """The tenant this unit of work is scoped to, or None if it is unscoped."""
    return _current_tenant_id.get()


def set_tenant_context(tenant_id: int | None) -> None:
    """Scope the current unit of work to a tenant. Used by the request path."""
    _current_tenant_id.set(tenant_id)


def clear_tenant_context() -> None:
    """Drop any tenant scope. Called from teardown so a pooled worker thread
    cannot carry one request's tenant into the next."""
    _current_tenant_id.set(None)


@contextmanager
def tenant_context(tenant_id: int):
    """Run a block scoped to `tenant_id`, restoring the previous scope after.

    Restoration rather than clear is what makes nesting safe: provisioning sets
    a tenant, then calls a seeder that nests its own scope, and the outer scope
    survives.
    """
    token = _current_tenant_id.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _current_tenant_id.reset(token)


@contextmanager
def bypass_tenant_filter():
    """Run a block across all tenants, unchanged.

    Every use is a deliberate, reviewable decision -- the leak audit reports
    them. Reserved for platform administration and cross-tenant reporting.
    """
    token = _current_tenant_id.set(None)
    try:
        yield
    finally:
        _current_tenant_id.reset(token)
