from sqlalchemy import event, inspect
from datetime import datetime, timezone
from src.api.models.platform_user_model import PlatformUser
## Shared with hotel users on purpose: an address that normalizes one way for a
## hotel login and another way for a platform login is a duplicate-account bug
## waiting to happen.
from src.api.events.user_events import normalize_email


### PlatformUser extends BaseModel, whose created_at / updated_at are
### nullable=False with no column default, so a row inserted without these
### listeners raises MySQLdb.IntegrityError 1048.


### BEFORE INSERT
@event.listens_for(PlatformUser, "before_insert")
def platform_user_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    target.created_at = now
    target.updated_at = now

    if target.email:
        target.email = normalize_email(target.email)

    ## Soft delete handling
    if target.is_deleted:
        if target.deleted_at is None:
            target.deleted_at = now
    else:
        target.deleted_at = None


### BEFORE UPDATE
@event.listens_for(PlatformUser, "before_update")
def platform_user_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    target.updated_at = now

    state = inspect(target)

    ## Normalize email (only if changed)
    if state.attrs.email.history.has_changes() and target.email:
        target.email = normalize_email(target.email)

    ## Soft delete handling
    if state.attrs.is_deleted.history.has_changes():
        if target.is_deleted:
            target.deleted_at = target.deleted_at or now
        else:
            target.deleted_at = None
