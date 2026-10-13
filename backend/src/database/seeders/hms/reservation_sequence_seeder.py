from sqlalchemy import select
from src.api.models import ReservationSequence, Prefixes
from src.database.session import db_session
from datetime import datetime, timezone

def seed_reservation_sequences():
    try:
        now = datetime.now()
        year = now.year
        month = now.month

        ## Fetch all active prefixes
        prefix_stmt = select(Prefixes).filter_by(is_active=True)
        prefixes = db_session().execute(prefix_stmt).scalars().all()

        for prefix in prefixes:

            ## Check if sequence already exists
            stmt = select(ReservationSequence).filter_by(
                prefix_id=prefix.id,
                reservation_year=year,
                reservation_month=month,
                is_deleted=False
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                sequence = ReservationSequence(
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
        print("!!! Error seeding reservation sequences:", str(e))

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_reservation_sequences()