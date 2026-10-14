from sqlalchemy import select
from src.api.models import ReservationSequence, Prefixes
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from datetime import datetime, timezone

def seed_reservation_sequences(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        now = datetime.now()
        year = now.year
        month = now.month

        ## Fetch this hotel's active prefixes. Scoped, so a second hotel gets
        ## its own sequence rows rather than silently counting on the first
        ## hotel's -- which would hand both hotels the same reservation numbers.
        prefix_stmt = select(Prefixes).filter_by(tenant_id=tenant_id, is_active=True)
        prefixes = db_session().execute(prefix_stmt).scalars().all()

        for prefix in prefixes:

            ## Check if sequence already exists
            stmt = select(ReservationSequence).filter_by(
                tenant_id=tenant_id,
                prefix_id=prefix.id,
                reservation_year=year,
                reservation_month=month,
                is_deleted=False
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                sequence = ReservationSequence(
                    tenant_id=tenant_id,
                    prefix_id=prefix.id,
                    reservation_year=year,
                    reservation_month=month,
                    last_sequence=0,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(sequence)

        db_session.commit()
        print("--- Reservation sequences seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding reservation sequences:", safe_error(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_reservation_sequences()
