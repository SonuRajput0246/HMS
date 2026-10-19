"""drop tenant suspension

Removes the tenant suspension flag: `tenants.is_suspended` and
`tenants.suspended_reason`, plus the `/suspend` and `/reactivate` platform
endpoints that wrote them.

Why: a hotel that is blocked is what `is_active = false` already expresses, and
carrying a second flag for the same decision meant two columns that could
disagree -- a hotel could read "active" in one place and "suspended" in another,
because `status` was derived from the pair while the resolver checked them
independently. Deactivation already stops the hotel, already survives a restart,
and already shows the operator which hotels are down; the reason string was the
only thing suspension added, and it belonged with the support call rather than
in the registry.

`is_active` and `is_deleted` remain the two lifecycle flags: the first is
provisioning state (the hotel keeps its rows and stops accepting logins), the
second is archiving (it leaves every list and its subdomain stops resolving).

No data is lost that matters -- an `is_suspended = true` row is migrated to
`is_active = false`, so a blocked hotel stays blocked rather than silently
becoming tradeable. Rows that were suspended *and* already inactive are
unaffected, and `suspended_reason` is dropped with the column it belonged to;
put the text in the audit trail or the support ticket instead, which is where a
reason is readable after the fact anyway.

The model, `tenant_events`, `tenant_resolver`, `tenant_management_service` and
`tenant_management_schema` have all been changed to match.

Revision ID: d7e4b2c9f016
Revises: c3a91f7be204
Create Date: 2026-10-19 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e4b2c9f016'
down_revision: Union[str, Sequence[str], None] = 'c3a91f7be204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    ## A blocked hotel must stay blocked. `is_suspended` is NOT NULL with no
    ## default in the old model, so this runs before the drop and the column
    ## being removed is exactly the one being read here.
    op.execute(
        "UPDATE tenants SET is_active = FALSE WHERE is_suspended = TRUE"
    )

    ## Columns are dropped, not nulled: leaving a dead `is_suspended` around is
    ## how the next reader comes to believe there are two lifecycle states.
    op.drop_column('tenants', 'suspended_reason')
    op.drop_column('tenants', 'is_suspended')


def downgrade() -> None:
    """Downgrade schema."""
    ## Recreating the columns is not restoring their values. `is_suspended`
    ## comes back false for every row -- a hotel that was blocked at upgrade time
    ## is already `is_active = false`, which the upgraded code refused anyway, so
    ## no hotel silently starts serving after a downgrade. The reasons are gone:
    ## they were only ever display text for a state that no longer exists.
    op.add_column(
        'tenants',
        sa.Column('is_suspended', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.add_column(
        'tenants',
        sa.Column('suspended_reason', sa.String(length=255), nullable=True),
    )
