from typing import TYPE_CHECKING

from src.database.base_model import BaseModel
from sqlalchemy import String, Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    pass


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

    `timezone` and `currency` are what the hotel actually trades in, and they
    live here rather than in configuration for the same reason CMS's do: a single
    process-wide setting cannot describe hotels in different zones or trading in
    different currencies. Both are registry facts the platform console sets at
    creation time. `timezone` is validated against the IANA database by the
    service that writes it, because a typo shifts every daily report figure;
    `currency` is an ISO 4217 code and is mirrored into the tenant's
    `system_settings.default_currency`, which is what the hotel-side code reads.

    `is_active` and `is_deleted` are the two lifecycle flags, and they mean
    different things. `is_active` is provisioning state: a deactivated hotel
    keeps every row it owns and simply stops accepting logins, and flipping it
    back re-opens the hotel. `is_deleted` is archiving -- the hotel leaves every
    list and its subdomain stops resolving, but nothing is destroyed and it can
    be restored.

    There is deliberately no third state. An earlier revision carried
    `is_suspended` / `suspended_reason` for an administrative block distinct from
    deactivation; it was removed as redundant, because a hotel that is blocked
    with a reason is exactly what `is_active = false` already expresses, and two
    flags for one decision is two that can disagree.
    """

    __tablename__ = 'tenants'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ## IANA zone the business trades in, e.g. "Asia/Kolkata". Reports bucket
    ## hourly aggregates by this, so an unset value shifts every closing-hour
    ## figure into the wrong day.
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Kolkata")

    ## ISO 4217 code, e.g. "INR". Drives currency formatting in the hotel UI and
    ## the reports' totals.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")


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
