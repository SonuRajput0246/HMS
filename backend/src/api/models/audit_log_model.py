from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base_model import BaseModel


class AuditLog(BaseModel):
    """Who did what to the platform, recorded at the point of the change.

    Global, like the platform admin who writes it: an audit trail is exactly the
    thing that must survive the tenant it describes being archived, so it cannot
    itself be tenant-scoped. `super_admin_id` is a plain integer with no foreign
    key on purpose -- the trail must outlive the admin account, and a deleted
    actor should leave the row readable rather than cascade it away. The actor's
    email is copied in at write time for the same reason.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    super_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ## A short verb, e.g. CREATE_TENANT, DEACTIVATE_TENANT, ARCHIVE_TENANT.
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    ## The kind of thing acted on, e.g. "tenant".
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ## Free-form context (changed fields, previous/next values) as JSON text.
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        ## "Show me the history of this tenant."
        Index("ix_audit_entity", "entity_type", "entity_id"),
        ## "Show me what this admin did, most recent first."
        Index("ix_audit_actor", "super_admin_id", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action!r}, entity={self.entity_type}:{self.entity_id})>"
