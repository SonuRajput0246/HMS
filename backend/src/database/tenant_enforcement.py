"""Deny-by-default tenant enforcement: one place that scopes every read, stamps
every write, and refuses a reference that reaches outside the current tenant.

Two listeners are installed on the SQLAlchemy `Session` class, so they cover
every session in the process -- request handlers, seeders, scripts -- rather
than each service having to remember a filter. A model that inherits
`TenantScoped` is therefore isolated the moment it is declared, and a service
that forgets to filter is still safe.

  `do_orm_execute`  decorates every ORM SELECT, bulk UPDATE and bulk DELETE with
                    `with_loader_criteria(TenantScoped, tenant_id == current)`.
                    `include_aliases=True` extends that to eager-loaded and
                    aliased occurrences, so a `lazy="joined"` parent cannot ride
                    along unfiltered. (`Session.get()` is the exception -- see
                    the next paragraph.)

  `Session.get`     is wrapped, because it checks the identity map *before* it
                    emits SQL, so loader criteria never run on an object this
                    session already holds. A row loaded under
                    `bypass_tenant_filter()` would otherwise stay visible after
                    the tenant switched. The wrapper returns `None` for an
                    identity-map hit that belongs to another tenant, which is
                    what the read filter would have done had a query run.

  `before_flush`    does two jobs on the rows about to be written:
                      * STAMP `tenant_id` on a new tenant-scoped row from the
                        current context, and refuse the write outright when there
                        is no context. An unscoped insert is a programming error,
                        not something to default to the first hotel.
                      * GUARD every tenant-scoped foreign key against pointing at
                        another tenant's row. The set of edges this applies to is
                        derived from the mapper, not written down: an edge is
                        guarded exactly when its target class inherits
                        `TenantScoped`. That is what keeps the five legitimate
                        tenant -> global edges (guest -> countries/cities/states,
                        role_module_access -> modules) allowed without naming
                        them, and a newly added model covered with no edit here.

`bypass_tenant_filter()` suppresses both the read filter and (by making the
context None) the stamp's requirement for a context -- it is for cross-tenant
reads only. A cross-tenant *write* still has to name its tenant with
`tenant_context(tenant_id)`, because a write with no tenant is always a bug.

The exceptions raised here are `RuntimeError` subclasses on purpose. A service
that wraps `commit()` in `except SQLAlchemyError` must not swallow them: a
cross-tenant reference is not a database fault to be retried, it is a refusal
that has to reach the caller.
"""
from functools import lru_cache

from sqlalchemy import Select, Update, Delete, event, inspect as sa_inspect, select
from sqlalchemy.orm import MANYTOONE, Session, lazyload, with_loader_criteria

from src.database.base import Base
from src.database.tenant_context import current_tenant_id
from src.database.tenant_scoped import TenantScoped


class TenantContextMissingError(RuntimeError):
    """A tenant-scoped row was written with no tenant in context."""


class CrossTenantReferenceError(RuntimeError):
    """A row was written that referenced another tenant's row."""


## ---------------------------------------------------------------------------
## read / bulk-write filtering
## ---------------------------------------------------------------------------

def _scope_to_tenant(state):
    if state.execution_options.get("skip_tenant_filter"):
        return

    tenant_id = current_tenant_id()
    if tenant_id is None:
        ## No scope: an explicit cross-tenant context, or a global/platform unit
        ## of work. Reads stay unfiltered by design; writes are refused in
        ## before_flush, so this cannot become a silent cross-tenant insert.
        return

    ## Only ORM SELECT/UPDATE/DELETE carry loader criteria. An INSERT has no
    ## WHERE, and a raw TextClause has no `.options()` at all.
    if not isinstance(state.statement, (Select, Update, Delete)):
        return

    state.statement = state.statement.options(
        with_loader_criteria(
            TenantScoped,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


## ---------------------------------------------------------------------------
## write stamping + foreign-key guard
## ---------------------------------------------------------------------------

def _stamp(obj, tenant_id):
    """Put the context tenant on a new row, or refuse the write."""
    if tenant_id is None:
        raise TenantContextMissingError(
            f"{type(obj).__name__} cannot be written with no tenant in context. "
            "Wrap the work in src.database.tenant_context.tenant_context(tenant_id), "
            "or set tenant_id explicitly inside that scope."
        )

    current = obj.tenant_id
    if current is None:
        obj.tenant_id = tenant_id
    elif current != tenant_id:
        raise CrossTenantReferenceError(
            f"{type(obj).__name__} is stamped tenant {current} but the current "
            f"tenant is {tenant_id}."
        )


@lru_cache(maxsize=1)
def _table_to_class():
    """Every mapped class, by table name. Built once, after models import."""
    return {mapper.class_.__tablename__: mapper.class_ for mapper in Base.registry.mappers}


@lru_cache(maxsize=None)
def _scoped_fk_targets(model):
    """The (attribute, target class) pairs on `model` that cross into a tenant.

    Derived from the mapper: a column is a guarded edge exactly when it carries a
    foreign key into a class that inherits `TenantScoped`. `tenant_id` itself is
    excluded -- it points at `tenants`, which is above every tenant.
    """
    mapper = sa_inspect(model)
    targets = []
    for col in mapper.columns:
        if col.name == "tenant_id":
            continue
        for fk in col.foreign_keys:
            target = _table_to_class().get(fk.column.table.name)
            if target is not None and issubclass(target, TenantScoped):
                targets.append((col.key, target))
    return tuple(targets)


def _resolve_references(session, target, ids, tenant_id):
    """Which of `ids` name a `target` row visible to `tenant_id`?

    Reads the answer from the session first -- an object already loaded, or one
    pending in this same flush, is the common case and costs no query. Anything
    left is looked up with an ORM SELECT, which the read filter has already
    scoped to the tenant, so a row from another tenant simply is not there.
    """
    mapper = sa_inspect(target)
    if len(mapper.primary_key) != 1:
        ## No composite-key model is a foreign-key target today; if one becomes
        ## one, this returns "found" rather than guessing and the database's own
        ## constraint is the backstop.
        return set(ids)

    pk = mapper.primary_key[0]
    found = {
        key[0]
        for key, obj in session.identity_map.items()
        if isinstance(obj, target) and key[0] in ids
    }
    for obj in session.new:
        if isinstance(obj, target) and getattr(obj, pk.key, None) in ids:
            found.add(getattr(obj, pk.key))

    remaining = ids - found
    if remaining:
        rows = session.execute(
            select(target).options(lazyload("*")).where(pk.in_(remaining))
        ).scalars().all()
        found.update(getattr(row, pk.key) for row in rows)
    return found


def _guard(session, pending, tenant_id):
    ## 1. Object-graph relationships assigned in Python. Cheap: the related
    ##    object is already in memory, so there is no query.
    for obj in pending:
        state = sa_inspect(obj)
        if tenant_id is not None and obj.tenant_id is not None and obj.tenant_id != tenant_id:
            raise CrossTenantReferenceError(
                f"{type(obj).__name__} would move to tenant {obj.tenant_id}, "
                f"but the current tenant is {tenant_id}."
            )
        for rel in state.mapper.relationships:
            if rel.direction is not MANYTOONE:
                continue
            if not issubclass(rel.mapper.class_, TenantScoped):
                continue
            if rel.key in state.unloaded:
                continue
            related = getattr(obj, rel.key, None)
            if related is not None and related.tenant_id != obj.tenant_id:
                raise CrossTenantReferenceError(
                    f"{type(obj).__name__}.{rel.key} points at "
                    f"{type(related).__name__} in tenant {related.tenant_id}, "
                    f"not tenant {obj.tenant_id}."
                )

    ## 2. Scalar foreign keys. Batch the lookups: one query per distinct target
    ##    class per flush, not one per row.
    wanted = {}
    for obj in pending:
        for attr, target in _scoped_fk_targets(type(obj)):
            value = getattr(obj, attr, None)
            if value is None:
                continue
            wanted.setdefault(target, {}).setdefault(value, []).append((obj, attr))

    for target, by_id in wanted.items():
        found = _resolve_references(session, target, set(by_id), tenant_id)
        for value, refs in by_id.items():
            if value not in found:
                obj, attr = refs[0]
                raise CrossTenantReferenceError(
                    f"{type(obj).__name__}.{attr}={value} is not a "
                    f"{target.__name__} in the current tenant."
                )


def _stamp_and_guard(session, flush_context, instances):
    tenant_id = current_tenant_id()

    for obj in session.new:
        if isinstance(obj, TenantScoped):
            _stamp(obj, tenant_id)

    pending = [o for o in session.new if isinstance(o, TenantScoped)]
    pending.extend(o for o in session.dirty if isinstance(o, TenantScoped))
    if pending:
        _guard(session, pending, tenant_id)


## ---------------------------------------------------------------------------
## Session.get(), which skips the filter when the object is already in memory
## ---------------------------------------------------------------------------

_session_get = Session.get


def _tenant_checked_get(self, entity, ident, *args, **kwargs):
    obj = _session_get(self, entity, ident, *args, **kwargs)

    ## `get` answers from the identity map first: if this session already holds
    ## the row, no statement is emitted and `do_orm_execute` never runs. The
    ## object can therefore belong to another tenant -- a row loaded under
    ## `bypass_tenant_filter()`, say -- while the current context is a tenant
    ## that must not see it. Answering `None` matches what the read filter does.
    tenant_id = current_tenant_id()
    if obj is not None and tenant_id is not None and isinstance(obj, TenantScoped):
        if obj.tenant_id != tenant_id:
            return None
    return obj


## ---------------------------------------------------------------------------
## installation
## ---------------------------------------------------------------------------

_installed = False


def install_tenant_enforcement():
    """Attach the listeners to the `Session` class, once.

    Class-level, so every session built anywhere in the process is covered --
    including the throwaway sessions a test or a script builds. Importing this
    module installs them; `src/database/session.py` imports it so that obtaining
    a session at all is what turns enforcement on.
    """
    global _installed
    if _installed:
        return
    _installed = True
    event.listen(Session, "do_orm_execute", _scope_to_tenant)
    event.listen(Session, "before_flush", _stamp_and_guard)
    Session.get = _tenant_checked_get


install_tenant_enforcement()
