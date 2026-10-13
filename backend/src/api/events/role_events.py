from sqlalchemy import event
from src.api.models import Role
from datetime import datetime, timezone



### BEFORE INSERT (Role)
@event.listens_for(Role, "before_insert")
def role_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE UPDATE (Role)
@event.listens_for(Role, "before_update")
def role_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now

    ## Soft delete handling
    if target.is_deleted and target.deleted_at is None:
        target.deleted_at = now