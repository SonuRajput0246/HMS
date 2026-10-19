"""platform super admin console

Replaces the prototype `platform_users` table with the full platform-console
schema ported from the CMS product:

  * `super_admin_users`   -- platform operators, with MFA enrolment and the
                             brute-force lockout columns the prototype lacked
  * `super_admin_tokens`  -- server-side session records, so logout and a
                             password reset actually revoke a token
  * `audit_logs`          -- the platform activity trail

It also adds `tenants.timezone` and `tenants.currency`. Those are the registry
facts the console sets at creation time; `BUSINESS_TIMEZONE` and the seeded
`default_currency` are what they default to, so existing hotels keep the
behaviour they had before the columns existed.

`platform_users` is dropped rather than migrated. Its rows were created by a
test script, it never held a working login (no token revocation, no MFA
enrolment), and carrying rows across would mean mapping a schema that shares
almost nothing with its replacement. Re-seed the first admin with
`python -m src.database.seeders.platform_admin_seeder` after upgrading.

A sibling revision, `d7e4b2c9f016`, drops `tenants.is_suspended` and
`tenants.suspended_reason`. Apply both: this one alone leaves `tenants` carrying
a column the models no longer declare, and `alembic check` will report the drift.

Revision ID: c3a91f7be204
Revises: 88048efa8f2c
Create Date: 2026-10-18 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a91f7be204'
down_revision: Union[str, Sequence[str], None] = '88048efa8f2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    ## ---- registry facts on `tenants` -------------------------------------
    ##
    ## server_default backfills every existing row, so the NOT NULL below lands
    ## without a separate data-migration step, and it stays on the column as the
    ## value a hotel gets when nothing supplies one. Both defaults mirror what
    ## the hotel already used process-wide, so no existing behaviour shifts.
    op.add_column(
        'tenants',
        sa.Column(
            'timezone',
            sa.String(length=50),
            server_default='Asia/Kolkata',
            nullable=False,
        ),
    )
    op.add_column(
        'tenants',
        sa.Column(
            'currency',
            sa.String(length=3),
            server_default='INR',
            nullable=False,
        ),
    )

    ## ---- platform operators ----------------------------------------------
    op.create_table(
        'super_admin_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=False),
        sa.Column('last_name', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_password_update_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False),
        sa.Column('mfa_secret', sa.String(length=32), nullable=True),
        ## server_default backfills existing rows, so the NOT NULL below lands
        ## without a separate data-migration step.
        sa.Column(
            'failed_login_attempts',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ux_super_admin_email', 'super_admin_users', ['email'], unique=True
    )
    op.create_index(
        'ix_super_admin_active_id',
        'super_admin_users',
        ['is_deleted', 'is_active', 'id'],
        unique=False,
    )

    ## ---- revocable platform sessions --------------------------------------
    op.create_table(
        'super_admin_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('super_admin_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.String(length=512), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['super_admin_id'], ['super_admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    ## The middleware's per-request revocation lookup.
    op.create_index(
        'ix_super_admin_token_live',
        'super_admin_tokens',
        ['super_admin_id', 'is_revoked'],
        unique=False,
    )

    ## ---- platform activity trail -----------------------------------------
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        ## Plain integer, no FK on purpose: the trail must outlive the admin
        ## account that wrote it.
        sa.Column('super_admin_id', sa.Integer(), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_audit_entity', 'audit_logs', ['entity_type', 'entity_id'], unique=False
    )
    op.create_index(
        'ix_audit_actor',
        'audit_logs',
        ['super_admin_id', 'created_at'],
        unique=False,
    )

    ## ---- drop the prototype ------------------------------------------------
    ##
    ## Dropped whole, index and all: `DROP TABLE` takes the indexes with it, and
    ## naming them first would be a second thing to keep in step.
    op.drop_table('platform_users')


def downgrade() -> None:
    """Downgrade schema."""
    ## Recreates the prototype table rather than restoring its rows: the rows
    ## were dropped on the way up and nothing carried them anywhere. Seed
    ## `platform_users` by hand if you need a platform login after downgrading.
    op.create_table(
        'platform_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=128), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=False),
        sa.Column('last_name', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False),
        sa.Column('mfa_secret', sa.String(length=32), nullable=True),
        sa.Column('last_password_update_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            'CHAR_LENGTH(TRIM(first_name)) > 0', name='ck_platform_user_first_name'
        ),
        sa.CheckConstraint(
            'CHAR_LENGTH(TRIM(last_name)) > 0', name='ck_platform_user_last_name'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_active_platform_user_email',
        'platform_users',
        ['is_deleted', 'email'],
        unique=False,
    )
    op.create_index(
        op.f('ix_platform_users_email'), 'platform_users', ['email'], unique=True
    )

    ## Tables are dropped whole rather than index-by-index-then-table.
    ## `ix_super_admin_token_live` is the index MySQL chose to back the
    ## `super_admin_tokens.super_admin_id` foreign key, so dropping it while the
    ## constraint still exists is refused with error 1553. `DROP TABLE` removes
    ## the indexes and the constraint together.
    op.drop_table('audit_logs')
    op.drop_table('super_admin_tokens')
    op.drop_table('super_admin_users')

    op.drop_column('tenants', 'currency')
    op.drop_column('tenants', 'timezone')
