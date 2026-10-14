from sqlalchemy import event, inspect
from datetime import datetime, timezone
from src.api.models.tenant_model import Tenant


### Tenant extends BaseModel, whose created_at / updated_at are nullable=False
### with no column default, so a row inserted without these listeners raises
### MySQLdb.IntegrityError 1048. Same reason every other model has an events
### module; see app.py.


### BEFORE INSERT
@event.listens_for(Tenant, "before_insert")
def tenant_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    target.created_at = now
    target.updated_at = now

    ## Soft delete handling
    if target.is_deleted:
        if target.deleted_at is None:
            target.deleted_at = now
    else:
        target.deleted_at = None

    ## A suspended tenant always carries a reason. Only the first suspension is
    ## recorded -- re-suspending without a new reason must not blank the one
    ## that explains the current outage.
    if not target.is_suspended:
        target.suspended_reason = None


### BEFORE UPDATE
@event.listens_for(Tenant, "before_update")
def tenant_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    target.updated_at = now

    state = inspect(target)

    ## Soft delete handling
    if state.attrs.is_deleted.history.has_changes():
        if target.is_deleted:
            target.deleted_at = target.deleted_at or now
        else:
            target.deleted_at = None

    ## Clearing suspension clears the reason with it, so a reactivated tenant
    ## cannot keep a stale explanation attached.
    if state.attrs.is_suspended.history.has_changes() and not target.is_suspended:
        target.suspended_reason = None
