from sqlalchemy import event, inspect
from datetime import datetime, timezone
from src.api.models.common.user_model import User


### COMMON HELPERS
def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if not email:
        raise ValueError("Email cannot be empty")
    return email


### BEFORE INSERT
@event.listens_for(User, "before_insert")
def user_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now

    ## Normalize email
    if target.email:
        target.email = normalize_email(target.email)

    ## Soft delete handling
    if target.is_deleted:
        if target.deleted_at is None:
            target.deleted_at = now
    else:
        target.deleted_at = None

    ## Deactivation handling
    if target.is_active is False:
        if target.deactivated_at is None:
            target.deactivated_at = now
    else:
        target.deactivated_at = None
        target.deactivated_by = None
        target.deactivation_reason = None


### BEFORE UPDATE
@event.listens_for(User, "before_update")
def user_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
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

    ## Deactivation handling
    if state.attrs.is_active.history.has_changes():
        if target.is_active is False:
            target.deactivated_at = target.deactivated_at or now
        else:
            target.deactivated_at = None
            target.deactivated_by = None
            target.deactivation_reason = None