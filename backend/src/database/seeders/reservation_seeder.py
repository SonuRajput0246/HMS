from datetime import datetime, timedelta
from sqlalchemy import select
from datetime import datetime, timezone
from src.api.models import Room, Prefixes, ReservationSequence
from src.api.models.reservation_model import Reservation
from src.database.session import db_session


reservations_data = [
    {
        "room_number": "201",
        "check_in_date": datetime.now() + timedelta(days=1),
        "check_out_date": datetime.now() + timedelta(days=3),
        "total_amount": 3000.00,
        "reservation_status": "reserved",
        "created_by": 1
    }
]


def seed_reservations():
    try:
        now = datetime.now()
        year = now.year
        month = now.month

        # 🔥 Get prefix (RES)
        prefix_stmt = select(Prefixes).filter_by(purpose="reservation", is_active=True)
        prefix = db_session().execute(prefix_stmt).scalar_one_or_none()

        if not prefix:
            print("!!! Prefix not found")
            return

        for reservation in reservations_data:

            # Fetch room
            room_stmt = select(Room).filter_by(
                room_number=reservation["room_number"],
                is_deleted=False
            )
            room = db_session().execute(room_stmt).scalar_one_or_none()

            if not room:
                continue

            # 🔥 Get or create sequence row (with lock)
            seq_stmt = select(ReservationSequence).filter_by(
                prefix_id=prefix.id,
                reservation_year=year,
                reservation_month=month
            ).with_for_update()

            sequence_row = db_session().execute(seq_stmt).scalar_one_or_none()

            if not sequence_row:
                sequence_row = ReservationSequence(
                    prefix_id=prefix.id,
                    reservation_year=year,
                    reservation_month=month,
                    last_sequence=0
                )
                db_session.add(sequence_row)
                db_session.flush()

            # 🔥 Increment sequence
            sequence_row.last_sequence += 1
            sequence = sequence_row.last_sequence

            # 🔥 Generate reservation number
            reservation_number = f"{prefix.code}-{year}{month:02d}-{sequence:05d}"

            # Create reservation
            new_reservation = Reservation(
                room_id=room.id,
                reservation_number=reservation_number,
                check_in_date=reservation["check_in_date"],
                check_out_date=reservation["check_out_date"],
                total_amount=reservation["total_amount"],
                reservation_status=reservation["reservation_status"],
                created_by=reservation["created_by"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            db_session.add(new_reservation)

        db_session.commit()
        print("--- Reservations seeded successfully with reservation numbers ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding reservations:", str(e))

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_reservations()