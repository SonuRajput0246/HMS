from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base_model import BaseModel


class SuperAdminToken(BaseModel):
    """A live platform-admin session, so logout can actually revoke.

    A signed JWT is valid until it expires on its own; without a server-side
    record, `logout` only deletes the copy the browser holds and a copied token
    keeps working. This table is the revocation list the platform middleware
    checks on every request -- the same shape as the tenant `tokens` table, kept
    separate so the two auth paths share nothing.
    """
    __tablename__ = "super_admin_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    super_admin_id: Mapped[int] = mapped_column(
        ForeignKey("super_admin_users.id"), nullable=False
    )
    access_token: Mapped[str] = mapped_column(String(512), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        ## The middleware's per-request lookup: (admin, is_revoked).
        Index("ix_super_admin_token_live", "super_admin_id", "is_revoked"),
    )

    def __repr__(self):
        return f"<SuperAdminToken(id={self.id}, super_admin_id={self.super_admin_id})>"
