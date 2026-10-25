from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base_model import BaseModel


class SuperAdminUser(BaseModel):
    """A platform operator: the account that manages tenants themselves.

    Deliberately NOT a `BaseTenantModel`: this account belongs to the platform,
    not to any one cafe. The tenant `users` table requires a `tenant_id` and is
    unique on `(tenant_id, email)`, so a global operator has no valid row there
    -- giving one a fabricated tenant would make it a customer account and drag
    it into every tenant-scoped query and JWT. Keeping it on `BaseModel` means
    the tenant filter never sees it, and a tenant JWT can never be minted from
    it (the tenant login only ever looks in `users`).

    Authentication is a separate path (`middlewares/super_admin_auth.py`) with a
    token scope of `super_admin`; the tenant middleware rejects it and this one
    rejects tenant tokens, so the two populations cannot cross.

    MFA is compulsory here (the login path refuses a password-only session),
    unlike the tenant `User`, where it is opt-in.
    """
    __tablename__ = "super_admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_password_update_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)

    ## Brute-force guard on sign-in. A wrong password increments
    ## `failed_login_attempts`; reaching `SUPER_ADMIN_MAX_LOGIN_ATTEMPTS`
    ## stamps `locked_until` and the counter resets, so each lockout buys a
    ## fresh window rather than counting once and staying locked. A successful
    ## sign-in clears both. Kept on the account row because a platform admin is
    ## a single known principal, not a stream of anonymous callers, and the
    ## lockout must survive a process restart.
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ## Platform admins are few and looked up only by email at sign-in.
        Index("ux_super_admin_email", "email", unique=True),
        ## The "list active admins" path, mirroring the tenant tables' shape.
        Index("ix_super_admin_active_id", "is_deleted", "is_active", "id"),
    )

    def __repr__(self):
        return f"<SuperAdminUser(id={self.id}, email={self.email!r})>"
