"""The marker that puts a model inside a tenant's boundary.

Inheriting this is the whole statement a model has to make to be isolated. It is
a plain mixin rather than a `BaseModel` subclass because the models that need it
do not share one base: most extend `BaseModel`, but `tokens`, `email_otps`,
`account_deletions`, `reservation_primary_guests`, `reservation_additional_guests`,
`prefixes` and `system_settings` extend `Base` directly (several have no
`is_deleted` / timestamps at all). A mixin composes with either.

It carries exactly one column.

`tenant_id` is NOT NULL -- a scoped row always belongs to exactly one hotel, and
the enforcement layer refuses an insert that cannot say which. The FK is
`ON DELETE CASCADE`, so deleting a tenant takes its rows with it rather than
leaving orphans that no tenant can see and no one can find.

Indexed because every tenant-scoped read filters on it, and an unindexed
discriminator turns each tenant's query into a full scan of everyone's rows.
"""
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class TenantScoped:
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
