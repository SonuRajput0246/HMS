from sqlalchemy import select
from src.api.models import Prefixes
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from datetime import datetime, timezone

prefixes_data = [
    {"code": "RES", "purpose": "reservation", "description": "For Reservation"},
    {"code": "INV", "purpose": "invoice", "description": "For Invoice"},
    {"code": "PAY", "purpose": "payment", "description": "For Payment"},
]

def seed_prefixes(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for pd in prefixes_data:
            ## Must match on `purpose`, not `code`: the old filter_by(code=purpose)
            ## never matched anything (code is 'RES', purpose is 'reservation'),
            ## so every run inserted a duplicate, and the later lookup by
            ## purpose then raised MultipleResultsFound.
            ##
            ## The tenant_id is equally load-bearing. Without it, seeding a
            ## second hotel would find the *first* hotel's "reservation" prefix,
            ## decide the row already exists, and skip -- leaving the new hotel
            ## with no prefix at all, so it could not number a single booking.
            stmt = select(Prefixes).filter_by(
                tenant_id=tenant_id,
                purpose=pd["purpose"],
                is_active=True,
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                prefix = Prefixes(
                    tenant_id=tenant_id,
                    code=pd["code"],
                    purpose=pd["purpose"],
                    description=pd["description"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(prefix)

        db_session.commit()
        print("--- Reservation prefixes seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding reservation prefixes:", safe_error(e))
        ## Re-raised, not swallowed. Provisioning treats a seeded tenant as
        ## ready to use, so a failure here has to stop the run rather than be
        ## reported as success.
        raise

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_prefixes()
