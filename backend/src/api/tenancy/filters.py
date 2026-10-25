"""Read-side tenant enforcement.

Every ORM statement is rewritten to add `tenant_id = <current tenant>` to each
tenant-scoped entity it touches. This is the mechanism that actually confines a
query to one tenant: the `tenant_id` foreign key in the schema only stops an
orphan row, and does nothing to stop `SELECT * FROM cms_orders` returning
another cafe's orders.

WHERE THE TENANT COMES FROM
---------------------------
`src/api/tenancy/context.py`. On a request, `authenticate()` puts the caller's
tenant on `g`. A public auth route (login, OTP) resolves the tenant from the
slug in the payload and sets it before it queries. Outside a request, a seeder
or a script sets it explicitly, or bypasses.

THE THREE CASES
---------------
  * bypassed -- no criterion. Only for tenant bootstrap, seeders/migrations and
    platform-admin endpoints, scoped by `bypass_tenant_filter()`.
  * tenant is None -- no criterion, i.e. UNFILTERED. This is what a script with
    no tenant sees. It is deliberately not an error, because the seeders
    legitimately run before any tenant exists; the cost is that a request which
    forgets to set the tenant is unscoped rather than empty, so `authenticate()`
    actually setting it is load-bearing.
  * tenant set -- the criterion is added.

WHAT IT COVERS
--------------
SELECT, and ORM-enabled UPDATE/DELETE, including the legacy `Query.update()`
and `Query.delete()` still used in the services. It does NOT cover:

  * `Session.get()` identity-map lookups -- there are none in this codebase;
  * raw `text()` SQL executed on its own. The only such statements are on
    global tables or inside `bypass_tenant_filter()`.

A new raw query against a tenant-scoped table must add `tenant_id` by hand.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from src.api.tenancy.context import get_current_tenant_id, is_tenant_filter_bypassed
from src.database.base_model import BaseTenantModel


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state) -> None:
    ## Lazy loads of a column or a relationship are already constrained by the
    ## parent row that triggered them. Re-adding the criterion here would
    ## duplicate the predicate and can break "load the object we just inserted".
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return

    ## Seeders, migrations, tenant bootstrap and platform-admin endpoints opt
    ## out explicitly. The bypass is scoped, so it cannot outlive its `with`.
    if is_tenant_filter_bypassed():
        return

    ## No tenant in context: leave the statement alone. See the module docstring
    ## for why this is not an error, and why it must not be reached on a request
    ## that authenticated.
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return

    ## One option on BaseTenantModel covers every tenant-scoped subclass, and
    ## cannot drift: a model is scoped by its base class, not by a hand-kept
    ## list. `include_aliases` extends it to aliased/joined entities.
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            BaseTenantModel,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )
