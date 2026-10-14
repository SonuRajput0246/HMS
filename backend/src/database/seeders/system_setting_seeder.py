from sqlalchemy import select
from src.api.models import SystemSetting
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session

system_setting_data = [
    {"key":"default_currency","value":"INR"}
]

def seed_system_settings(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for ss in system_setting_data:
            ## Modern 2.0 syntax: Check if category exists.
            ##
            ## `key` is unique *within* a hotel, not across the install -- the
            ## primary key is (tenant_id, key). So the tenant filter is part of
            ## the identity of the row being looked up, not an optimization:
            ## without it the second hotel would read the first hotel's
            ## `default_currency` and skip creating its own.
            stmt = select(SystemSetting).filter_by(
                tenant_id=tenant_id,
                key=ss["key"],
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                system_setting = SystemSetting(
                    tenant_id=tenant_id,
                    key=ss["key"],
                    value=ss["value"]
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
