from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base_model import BaseModel

if TYPE_CHECKING:
    pass


class Tenant(BaseModel):
    """One customer of the platform -- a single cafe, in the general case.

    This is the only row in the database that is not itself scoped to a tenant.
    Everything else either hangs off `tenant_id` or is shared reference data
    (countries, currencies, the module/menu tree, enum definitions).

    `slug` is the login code a user types to say which cafe they are logging
    into. It is unique across all tenants and is the only tenant identifier
    that is safe to put in a URL or a form, because unlike the numeric id it
    carries no information and cannot be guessed to enumerate accounts.

    Why timezone and currency live here rather than in configuration:
    `BUSINESS_TIMEZONE` was a single env var, and every report's day boundary
    is computed against it. Two cafes in different zones -- or trading in
    different currencies -- cannot share one process-wide setting, so both
    moved onto the tenant. The config value survives as the default applied to
    newly created tenants.

    Deliberately NOT extending BaseTenantModel: a tenant cannot belong to a
    tenant. The whole scope of this table is the single tenant it describes.
    """
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)

    ## Human name, e.g. "Sunrise Cafe". Shown in the UI and in the email footer.
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    ## The login code, e.g. "sunrise". Lowercase, no spaces; the frontend and
    ## the login schema both normalise before comparing.
    slug: Mapped[str] = mapped_column(String(50), nullable=False)

    ## IANA zone the business trades in, e.g. "Asia/Kolkata". Reports bucket
    ## hourly aggregates by this, so an unset value shifts every closing-hour
    ## figure into the wrong day.
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)

    ## ISO 4217 code, e.g. "INR". Drives currency formatting in the POS and
    ## the reports' totals.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    ## A deactivated tenant keeps its rows (orders, invoices, audit trail) and
    ## simply stops accepting logins. Deleting a cafe's sales history is not
    ## something a flag flip should be able to do, so there is no hard-delete
    ## path here.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        ## No tenant index here, and there must never be one: this table
        ## has no tenant_id column. It IS the tenant.
        ## Login is by slug, so this is the hot path for every sign-in.
        Index("ux_tenant_slug", "slug", unique=True),
        ## Tenant pickers list active tenants only.
        Index("ix_tenant_active_id", "is_deleted", "is_active", "id"),
        ## The admin "search tenants" box.
        Index("ix_tenant_name", "is_deleted", "name"),
    )

    def __repr__(self):
        return f"<Tenant(id={self.id}, slug={self.slug!r}, name={self.name!r})>"
