from sqlalchemy import select
from src.api.extensions import bcrypt
from src.api.models.user_model import User
from src.api.models.role_model import Role
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from datetime import datetime, timezone

## Defaults for the local-development bootstrap. `provision_tenant` passes the
## credentials of the hotel being created; these exist so that running the
## seeders by hand on a fresh machine still produces an account you can sign in
## with, instead of a hotel nobody can enter.
ADMIN_EMAIL = "sonurajput8454@gmail.com"
ADMIN_PASSWORD = "123456"


def seed_super_admin(
    tenant_id: int | None = None,
    email: str = ADMIN_EMAIL,
    password: str = ADMIN_PASSWORD,
    first_name: str = "Super",
    last_name: str = "Admin",
    role_code: str = "SUPER_ADMIN",
):
    """Create one hotel's super admin -- the first account that can sign in.

    This is the *tenant's* top user, not the platform operator. A platform admin
    is a different table (`platform_users`) with a different secret and its own
    routes; it is never created here. The name is kept because within a hotel
    the granted role really is SUPER_ADMIN.

    Credentials are parameters now. They used to be the module constants above,
    which is fine for one developer's machine and wrong the moment a second
    hotel exists -- every hotel would share a login.
    """
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        ## Get Super Admin role, from this hotel's own copy of it. Looked up by
        ## role_code rather than role_name: the code is the stable contract,
        ## and an admin is free to rename the role to "Owner" in the UI.
        role_stmt = select(Role).filter_by(
            tenant_id=tenant_id,
            role_code=role_code,
            is_deleted=False
        )
        super_admin_role = db_session.execute(role_stmt).scalar_one_or_none()
        if not super_admin_role:
            ## Raised, not returned. Provisioning reports a tenant as ready only
            ## when its admin exists, so a silent skip here would hand the
            ## operator a hotel with no way in.
            raise RuntimeError(
                f"'{role_code}' role not found in tenant {tenant_id}. "
                f"Run seed_roles() for this tenant before its admin user."
            )

        ## Start seeding Super Admin.
        ##
        ## Filter on `email`, the parameter. This used to filter on the literal
        ## string "ADMIN_EMAIL", which can never match any row, so the existence
        ## check always reported "not found" and inserted a new super admin on
        ## every single run.
        ##
        ## `.first()` rather than `scalar_one_or_none()`: this is an existence
        ## check, so one row is all it needs. scalar_one_or_none() additionally
        ## asserts uniqueness, which turned databases already carrying the
        ## duplicates this bug created into a hard failure -- the seeder could
        ## never recover from its own past. Duplicates are reported instead.
        user_stmt = select(User).filter_by(
            tenant_id=tenant_id,
            email=email,
            is_deleted=False
        )
        existing_admins = db_session.execute(user_stmt).scalars().all()

        if len(existing_admins) > 1:
            print(
                f"!!! WARNING: {len(existing_admins)} active users share the "
                f"super admin email {email} in tenant {tenant_id}. Only the "
                f"first is kept; the rest are leftovers from a previous "
                f"seeding bug. Remove them: "
                f"DELETE FROM users WHERE email = '{email}' AND tenant_id = "
                f"{tenant_id} AND id > {existing_admins[0].id};"
            )

        existing_admin = existing_admins[0] if existing_admins else None

        if not existing_admin:
            ## Create Super Admin user
            hashed_password = bcrypt.generate_password_hash(password, 12).decode("utf-8")
            super_user = User(
                tenant_id=tenant_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=hashed_password,
                role_id=super_admin_role.id,
                is_email_verified=True,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db_session.add(super_user)
            db_session.commit()
            print(f"--- Super Admin user created successfully for tenant {tenant_id}. ---")
        else:
            print(f"Super Admin ({email}) already exists. Skipping...")
    except Exception as e:
        db_session.rollback()
        ## Raise rather than print-and-return, consistent with the other
        ## seeders. A silently skipped super admin is an app nobody can log
        ## into, and that should stop the run rather than look like success.
        print(f"!!! Super Admin seeder FAILED: {safe_error(e)}")
        raise
    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_super_admin()
