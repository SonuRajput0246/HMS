from sqlalchemy import select
from src.api.models import SystemSetting, Tenant
from src.api.utils.tenant_settings import DEFAULT_SETTINGS
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session


def seed_system_settings(tenant_id: int | None = None):
    """Seed the settings every hotel starts with.

    The data lives in `tenant_settings.DEFAULT_SETTINGS`, not here, because the
    read path applies the same defaults when a row is missing -- one definition
    instead of two that can drift.

    `company_name` is the exception: it is resolved to the hotel's own display
    name, so a freshly provisioned hotel sends mail that names it without
    anyone editing a setting first. An existing `company_name` is never
    overwritten, so an admin's later edit survives a re-run.
    """
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        tenant = db_session.execute(
            select(Tenant).filter_by(id=tenant_id)
        ).scalar_one_or_none()

        rows = dict(DEFAULT_SETTINGS)
        if tenant is not None:
            rows["company_name"] = tenant.name

        for key, value in rows.items():
            ## Modern 2.0 syntax: Check if category exists.
            ##
            ## `key` is unique *within* a hotel, not across the install -- the
            ## primary key is (tenant_id, key). So the tenant filter is part of
            ## the identity of the row being looked up, not an optimization:
            ## without it the second hotel would read the first hotel's
            ## `default_currency` and skip creating its own.
            stmt = select(SystemSetting).filter_by(
                tenant_id=tenant_id,
                key=key,
            )
            exists = db_session.execute(stmt).scalar_one_or_none()

            if not exists:
                system_setting = SystemSetting(
                    tenant_id=tenant_id,
                    key=key,
                    value=value,
                )
                db_session.add(system_setting)

        db_session.commit()
        print("--- System settings seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding system settings:", safe_error(e))
        raise

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_system_settings()
