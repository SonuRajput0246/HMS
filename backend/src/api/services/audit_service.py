"""Reading (and reusing the writer for) the platform audit trail.

`TenantManagementService` already writes an `AuditLog` row for every tenant
lifecycle action, but nothing has ever read them back -- the table carried two
purpose-built indexes (`ix_audit_entity`, `ix_audit_actor`) for queries no code
made. This service is that reader.

It also holds the single `write()` the newer platform actions share, so there is
one definition of "record an audit row" rather than a copy per service. The
tenant service keeps its own private `_audit` rather than being refactored onto
this one: that method is working, in production shape, and the value of not
disturbing it is higher than the value of one shared helper. Both write the same
row to the same table, so the reader here sees every action regardless of who
wrote it.

Audit writes are best-effort by design: a missing diagnostic row is a gap, a
rolled-back activation is a surprise. `write()` never raises into its caller.
"""
import json
import logging
from datetime import datetime, timezone

from flask import has_request_context, request

from src.api.models.audit_log_model import AuditLog


def _as_utc(value: datetime | None) -> datetime | None:
    """A filter boundary with no offset is read as UTC.

    The column is timezone-aware; comparing it against a naive literal would
    either fail on a strict backend or, worse, be compared as if it were local
    time. Treating an offset-less filter as UTC matches how the rows are
    written.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class AuditService:
    def __init__(self, db):
        self.db = db

    ## ---------------------------------------------------------------- read
    def get_logs(self, data: dict):
        """Newest-first platform activity, optionally narrowed by filter.

        Returns the same `{status, data, meta}` shape the tenant list uses, so
        the console's paginator is one component across both screens.
        """
        page_size = data["page_size"]
        page_number = data["page_number"]

        query = self.db.query(AuditLog)

        if data.get("action"):
            query = query.filter(AuditLog.action == data["action"])
        if data.get("entity_type"):
            query = query.filter(AuditLog.entity_type == data["entity_type"])
        if data.get("entity_id") is not None:
            query = query.filter(AuditLog.entity_id == data["entity_id"])
        if data.get("super_admin_id") is not None:
            query = query.filter(AuditLog.super_admin_id == data["super_admin_id"])

        date_from = _as_utc(data.get("date_from"))
        if date_from is not None:
            query = query.filter(AuditLog.created_at >= date_from)
        date_to = _as_utc(data.get("date_to"))
        if date_to is not None:
            query = query.filter(AuditLog.created_at <= date_to)

        total_records = query.count()
        logs = (
            query
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        last_page = (total_records + page_size - 1) // page_size if total_records > 0 else 1

        return {
            "status": True,
            "data": [self._serialize(log) for log in logs],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size,
            },
        }, 200

    ## --------------------------------------------------------------- write
    def write(self, actor, action: str, entity_type: str, entity_id, details: dict,
              actor_email: str | None = None) -> None:
        """Record one platform action. Never fails the operation -- see the
        module docstring. `details` is stored as JSON text, matching how the
        tenant service writes it, so one row shape covers every writer.

        `actor_email` overrides the address taken from `actor`. It exists for
        the one write that has no actor row to read: a sign-in attempt against
        an address that matches no account. There the email *is* the only thing
        the caller claimed, so it is recorded verbatim rather than dropped.
        """
        try:
            self.db.add(AuditLog(
                super_admin_id=getattr(actor, "id", None),
                actor_email=actor_email or getattr(actor, "email", None),
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=json.dumps(details, default=str) if details else None,
                ip_address=self._client_ip(),
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logging.exception("Failed to write audit log for %s on %s %s", action, entity_type, entity_id)

    ## ------------------------------------------------------------ helpers
    @staticmethod
    def _client_ip():
        if not has_request_context():
            return None
        return request.remote_addr

    @staticmethod
    def _serialize(log: AuditLog) -> dict:
        return {
            "id": log.id,
            "super_admin_id": log.super_admin_id,
            "actor_email": log.actor_email,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
