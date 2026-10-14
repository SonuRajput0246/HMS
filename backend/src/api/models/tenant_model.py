from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy import String, Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    from src.api.models.platform_user_model import PlatformUser


class Tenant(BaseModel):
    """One hotel. The isolation boundary for every tenant-scoped row.

    Every table in the tenancy boundary carries a `tenant_id` pointing here, so
    this row is what "the current tenant" means.

    `slug` is a DNS label, not a free-form name: it is the subdomain the hotel
    logs in on (acme.hms.example.com) and the value carried in the X-Tenant
    header and the JWT claim. It is therefore constrained to lowercase letters,
    digits and hyphens -- see ck_tenant_slug_format -- because a slug that is no
    longer a valid DNS label stops resolving, and the failure looks like an
    outage rather than a bad input.

    `is_active` and `is_suspended` are deliberately separate. `is_active` means
    provisioned and usable; `is_suspended` means administratively blocked, with
    the reason kept for the support call that follows. A tenant can be both
    active and suspended, and suspension is reversible without touching
    provisioning state.
    """

    __tablename__ = 'tenants'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suspended_reason: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)


    __table_args__ = (
        ## Structural check only: 1-63 characters, lowercase alphanumeric, and
        ## any hyphen must be interior. Real validation stays in the schema
        ## layer, which can say which rule was broken; the database only refuses
        ## the insert. Mirrors the ck_user_email_format precedent.
        CheckConstraint(
            "slug REGEXP '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'",
            name="ck_tenant_slug_format",
        ),

        ## Resolution runs on every request that names a tenant, and looks this
        ## up by slug. The unique index on slug alone does not include
        ## is_deleted, which every lookup filters on.
        Index("ix_active_tenant_slug", "is_deleted", "slug"),
    )

    def __repr__(self):
        return f"Tenant(id={self.id}, slug='{self.slug}')"
