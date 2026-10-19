"""Timestamp and soft-delete maintenance for the platform's global tables.

These three models carry no `tenant_id`, so nothing in
`src/database/tenant_enforcement.py` touches them -- but they do extend
`BaseModel`, whose `created_at` / `updated_at` are `nullable=False` with no
column default. A row inserted without a listener here raises
`MySQLdb.IntegrityError 1048` on MySQL, the same failure the per-model listeners
in this package exist to prevent for the hotel tables.

Imported for side effect from app.py alongside the other `*_events` modules;
registering the listeners is what this module does, not what it exposes.

`super_admin_users` additionally normalizes its email on the same rules as
`users` (`normalize_email`, shared with user_events). An address that normalizes
one way for a hotel login and another way for a platform login is a
duplicate-account bug waiting to happen.
"""
from datetime import datetime, timezone

from sqlalchemy import event, inspect

from src.api.events.user_events import normalize_email
from src.api.models.audit_log_model import AuditLog
from src.api.models.super_admin_token_model import SuperAdminToken
from src.api.models.super_admin_user_model import SuperAdminUser


## ------------------------------------------------------------------ stamping
def _before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)
    target.created_at = now
    target.updated_at = now

    if target.is_deleted:
        if target.deleted_at is None:
            target.deleted_at = now
    else:
        target.deleted_at = None

    if isinstance(target, SuperAdminUser) and target.email:
        target.email = normalize_email(target.email)


def _before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)
    target.updated_at = now

    state = inspect(target)
    if state.attrs.is_deleted.history.has_changes():
        if target.is_deleted:
            target.deleted_at = target.deleted_at or now
        else:
            target.deleted_at = None

    if isinstance(target, SuperAdminUser) and target.email:
        if state.attrs.email.history.has_changes():
            target.email = normalize_email(target.email)


event.listen(SuperAdminUser, "before_insert", _before_insert)
event.listen(SuperAdminUser, "before_update", _before_update)
event.listen(SuperAdminToken, "before_insert", _before_insert)
event.listen(SuperAdminToken, "before_update", _before_update)
event.listen(AuditLog, "before_insert", _before_insert)
event.listen(AuditLog, "before_update", _before_update)
