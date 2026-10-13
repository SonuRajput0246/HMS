from sqlalchemy import select
from src.api.models import SystemSetting
from src.database.session import db_session

system_setting_data = [
    {"key":"default_currency","value":"INR"}
]

def seed_system_settings():
    try:
        for ss in system_setting_data:
            ## Modern 2.0 syntax: Check if category exists
            stmt = select(SystemSetting).filter_by(key=ss["key"])
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                system_setting = SystemSetting(
                    key=ss["key"],
                    value=ss["value"]
                )
                db_session.add(system_setting)

        db_session.commit()
        print("--- System settings seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding system settings:", str(e))

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_system_settings()