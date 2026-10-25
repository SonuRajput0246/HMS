"""The single-use link that turns a provisioned tenant into a usable one.

When the platform registers a hotel, no `users` row exists yet -- only the
invitation below. The administrator's account is created at the moment the
invitation is accepted (see src/api/services/tenant_invitation_service.py),
so this row is the promise of that account rather than a placeholder for it.

Deliberately NOT extending BaseTenantModel:

  * it is written by the platform during provisioning, before any tenant
    context is bound, and read again by the *public* accept endpoint, where
    no tenant is bound either -- so the automatic read filter would never
    apply to either access and would buy nothing but a second `tenant_id`
    declaration;
  * `tenant_id` is therefore declared explicitly, NOT NULL with a foreign
    key, and every query here states its own criterion. The row still
    belongs to exactly one tenant -- the enforcement lives in the queries
    rather than in a base class that neither access path activates.

SECURITY: only `token_hash` is stored. The raw token exists exactly once,
in memory, and travels only in the emailed link -- `hash_value()` (SHA-256)
is the same one-way helper the OTP table uses. A leak of this table
therefore does not leak working invitation links.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base_model import BaseModel


class TenantAdminInvitation(BaseModel):
    __tablename__ = "tenant_admin_invitations"

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )

    ## The invited administrator, copied at issue time. `email` is the
    ## identity the account is created under on acceptance; the names
    ## prefill the account so the first sign-in needs no data entry.
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    ## SHA-256 of the raw token. Unique across the table because a token
    ## identifies exactly one invitation, whatever its tenant.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    ## Naive UTC (see src/api/utils/datetime_helper): MySQL DATETIME carries
    ## no offset, so the comparison on accept must use `utcnow()` too.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    ## Stamped at acceptance, in the same transaction that creates the user.
    ## NULL until then; a non-NULL value is what makes the token single-use.
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ## The platform operator who issued it (email copied at write time, the
    ## same snapshot idea as `audit_logs.actor_email`). NULL when a script
    ## or seeder issued it.
    invited_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        ## The lookup key for both public endpoints (preview, accept):
        ## one indexed equality on the hashed token.
        Index("ux_invitation_token_hash", "token_hash", unique=True),
        ## "Show me this tenant's invitations", newest first, live rows.
        Index("ix_invitation_tenant_status", "tenant_id", "is_deleted", "id"),
        ## Resend and duplicate checks by address within a tenant.
        Index("ix_invitation_tenant_email", "tenant_id", "email"),
    )

    def __repr__(self):
        return (
            f"<TenantAdminInvitation(id={self.id}, tenant_id={self.tenant_id}, "
            f"email={self.email!r})>"
        )
