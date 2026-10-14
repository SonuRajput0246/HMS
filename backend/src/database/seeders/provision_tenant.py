"""Create a hotel, and everything it needs before anyone can log into it.

This is the one place that writes a `tenants` row, so it is also the one place
that has to decide what a brand-new hotel starts with. The answer is
deliberately small: the roles its staff will be assigned, the document prefixes
and numbering sequences its bookings need, the setting and template defaults,
the login slides, and one admin user.

Everything else a hotel will eventually contain -- rooms, stock, guests,
reservations -- starts **empty**. Padding a paying customer's system with
another hotel's furniture is worse than showing them an empty screen, and it has
to be deleted before they can trust the numbers.

`seed_tenant_defaults` is idempotent: every seeder it calls checks for its own
rows before inserting. Re-running provisioning against an existing tenant tops
it up rather than duplicating it, which is what makes a half-finished provision
recoverable by simply running it again.

Local development's sample hotel is NOT built here. See
`run_base_seeders.seed_tenant_demo_data`; a tenant created in production never
sees it.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from src.api.models import Tenant
from src.database.seeders.login_slider_seeder import seed_login_sliders
from src.database.seeders.prefixes_seeder import seed_prefixes
from src.database.seeders.reservation_sequence_seeder import seed_reservation_sequences
from src.database.seeders.role_seeder import seed_roles
from src.database.seeders.super_admin_seeder import seed_super_admin
from src.database.seeders.system_setting_seeder import seed_system_settings
from src.database.seeders.template_seeder import seed_templates
from src.database.session import db_session
from src.database.tenant_context import tenant_context


def get_or_create_tenant(slug: str, name: str) -> Tenant:
    """The tenant with this slug, creating it if it is new.

    Lookup is by `slug` because slug is the tenant's identity: it is the
    subdomain and the JWT claim, so it is the thing callers already hold. `name`
    is only a label, and is refreshed when it differs -- nothing depends on it
    holding still, and a stale display name is worse than a write.

    The row is committed before any seeding starts. Seeders each own their
    session and commit independently, so a tenant that is not durable first
    would leave the seeded rows pointing at an id that no longer exists.
    """
    tenant = db_session.execute(
        select(Tenant).filter_by(slug=slug, is_deleted=False)
    ).scalar_one_or_none()

    if tenant is not None:
        if tenant.name != name:
            tenant.name = name
            tenant.updated_at = datetime.now(timezone.utc)
            db_session.commit()
        return tenant

    tenant = Tenant(
        slug=slug,
        name=name,
        is_active=True,
        is_suspended=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


def seed_tenant_defaults(tenant_id: int) -> None:
    """Seed the rows every working hotel needs, and only those.

    Order is dependency order, not alphabetical: `prefixes` before
    `reservation_sequences`, because a sequence belongs to a prefix and the
    sequence seeder resolves prefixes by id. `roles` is last only because it is
    the heaviest -- it reads the global `modules` tree, which `seed_platform_data`
    must have seeded already or every role comes out with no permissions.
    """
    with tenant_context(tenant_id):
        seed_prefixes(tenant_id)
        seed_reservation_sequences(tenant_id)
        seed_system_settings(tenant_id)
        seed_templates(tenant_id)
        seed_login_sliders(tenant_id)
        seed_roles(tenant_id)


def provision_tenant(
    slug: str,
    name: str,
    admin_email: str,
    admin_password: str,
    admin_first_name: str = "Hotel",
    admin_last_name: str = "Admin",
    role_code: str = "SUPER_ADMIN",
) -> Tenant:
    """A working, empty, isolated hotel with one admin who can sign in.

    Returns the tenant so the caller can report or redirect to it. Raises if the
    admin could not be created -- a hotel nobody can log into is not provisioned,
    and reporting success there would be a lie the support queue then has to
    untangle.
    """
    tenant = get_or_create_tenant(slug, name)

    ## Capture the id now, as a plain int. Every seeder below closes its session
    ## via db_session.remove() when it finishes, which detaches this instance --
    ## so reading `tenant.id` after the first seeder raises DetachedInstanceError
    ## instead of returning a number. The id does not go stale; the ORM object
    ## does.
    tenant_id = tenant.id

    with tenant_context(tenant_id):
        seed_tenant_defaults(tenant_id)
        seed_super_admin(
            tenant_id,
            email=admin_email,
            password=admin_password,
            first_name=admin_first_name,
            last_name=admin_last_name,
            role_code=role_code,
        )

    ## Re-read and then detach. Every seeder closes the session, and
    ## Session.close() expires the objects it holds -- so an instance left
    ## attached here would blow up with DetachedInstanceError the moment a later
    ## seeder, or the request teardown, closes the session again. Expunging
    ## yields a plain, fully-loaded object whose fields stay safe to read.
    tenant = db_session.execute(
        select(Tenant).filter_by(id=tenant_id)
    ).scalar_one()
    db_session.expunge(tenant)
    db_session.remove()
    return tenant
