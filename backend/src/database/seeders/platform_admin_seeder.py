"""Creates the platform (super admin) account.

This is the account that signs in on the bare domain and manages hotels, so it
belongs to the platform and not to any tenant: it is written to
`super_admin_users`, a `BaseModel` table with no `tenant_id`. That is also why
this runs as a GLOBAL seeder, before any tenant rather than per tenant -- there
is no `tenant_context` around it and none is wanted.

Reuses the shared password hashing so a platform password is stored exactly like
every other, and is idempotent on email: re-running refreshes nothing and never
duplicates the row.

Credentials come from configuration (see BaseConfig) rather than being
hardcoded, so a real deployment cannot be seeded with a well-known password by
oversight. The defaults exist so a fresh database is reachable at all and MUST be
changed before exposure.

Note what this account can do once signed in: nothing, on its own. MFA is
compulsory for platform administrators, so the first login hands back a fresh
secret and a pending token rather than a session. That is the correct shape --
this seeder creates the principal, not a bypass.

    python -m src.database.seeders.platform_admin_seeder
"""
from datetime import datetime, timezone

from sqlalchemy import select

from src.api.extensions import bcrypt
from src.api.models.super_admin_user_model import SuperAdminUser
from src.config import get_config
from src.database.session import db_session


def seed_platform_admin():
    config = get_config()
    email = (config.PLATFORM_ADMIN_EMAIL or "").strip().lower()

    try:
        if not email:
            ## Fail loudly rather than seeding nothing: an install with no
            ## platform admin has no way to create its first hotel.
            raise RuntimeError("PLATFORM_ADMIN_EMAIL is empty; cannot seed.")

        existing = db_session.execute(
            select(SuperAdminUser).filter_by(email=email, is_deleted=False)
        ).scalars().first()

        if existing is not None:
            print(f"Platform admin ({email}) already exists. Skipping...")
            return

        hashed = bcrypt.generate_password_hash(config.PLATFORM_ADMIN_PASSWORD, 12).decode("utf-8")
        db_session.add(SuperAdminUser(
            first_name=config.PLATFORM_ADMIN_FIRST_NAME,
            last_name=config.PLATFORM_ADMIN_LAST_NAME,
            email=email,
            password=hashed,
            is_active=True,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        db_session.commit()
        print(f"--- Platform admin created: {email}. ---")

    except Exception as exc:
        db_session.rollback()
        print(f"!!! Platform admin seeder FAILED: {str(exc)[:300]}")
        raise
    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_platform_admin()
