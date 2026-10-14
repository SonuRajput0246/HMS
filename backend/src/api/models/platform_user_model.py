from datetime import datetime
from src.database.base_model import BaseModel
from sqlalchemy import String, Boolean, DateTime, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column


class PlatformUser(BaseModel):
    """An operator of the platform itself: creates and administers tenants.

    Deliberately NOT a row in `users`. A platform admin exists above every
    tenant, so filing one under `users` would force `users.tenant_id` to be
    nullable and give that column two meanings -- "the hotel this belongs to"
    and "there is no hotel, this is the platform". One nullable column is the
    difference between "a missing filter returns nothing" and "a missing filter
    returns the highest-privilege accounts in the system". Keeping this table
    separate lets `users.tenant_id` stay NOT NULL and the invariant stay
    absolute.

    These rows never authenticate through the tenant login route. They have their
    own secret and their own routes; see PLATFORM_JWT_SECRET_KEY.
    """

    __tablename__ = 'platform_users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    last_password_update_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


    __table_args__ = (
        ## Same structural floor as `users`: a name that is present must not be
        ## blank. Platform admins are few and high-privilege, and a blank name
        ## makes an audit trail unreadable.
        CheckConstraint("CHAR_LENGTH(TRIM(first_name)) > 0", name="ck_platform_user_first_name"),
        CheckConstraint("CHAR_LENGTH(TRIM(last_name)) > 0", name="ck_platform_user_last_name"),

        Index("ix_active_platform_user_email", "is_deleted", "email"),
    )

    def __repr__(self):
        return f"PlatformUser(id={self.id}, email='{self.email}')"
