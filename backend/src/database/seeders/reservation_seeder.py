from datetime import datetime, timedelta
from sqlalchemy import select
from datetime import datetime, timezone
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.api.models import Room, Prefixes, ReservationSequence, User
from src.api.models.reservation_model import Reservation
from src.database.session import db_session


reservations_data = [
    {
        "room_number": "201",
        "check_in_date": datetime.now() + timedelta(days=1),
        "check_out_date": datetime.now() + timedelta(days=3),
        "total_amount": 3000.00,
        "reservation_status": "reserved",
    }
]


def seed_reservations(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        now = datetime.now()
        year = now.year
        month = now.month

        ## Reservations.created_by is a NOT NULL foreign key to users.id, so the
        ## demo booking has to be attributed to a real user *of this hotel*.
        ## This used to be a hardcoded `created_by: 1`, which is only correct on
        ## the database where user 1 happens to be the hotel's admin. On a fresh
        ## install that row may not exist at all, and under tenancy user 1 may
        ## belong to a different hotel -- which is a cross-tenant reference, not
        ## just a broken one.
        acting_user = db_session.execute(
            select(User).filter_by(
                tenant_id=tenant_id, is_deleted=False
            ).order_by(User.id)
        ).scalars().first()

        if not acting_user:
            raise RuntimeError(
                f"No user exists in tenant {tenant_id} to attribute the demo "
                f"reservation to. Seed this tenant's admin user first."
            )

        # Get prefix (RES) for this hotel
        prefix_stmt = select(Prefixes).filter_by(
            tenant_id=tenant_id,
            purpose="reservation",
            is_active=True
        )
        prefix = db_session().execute(prefix_stmt).scalar_one_or_none()

        if not prefix:
            print("!!! Prefix not found")
            return

        for reservation in reservations_data:

            # Fetch room. Scoped, so room 201 is this hotel's 201.
            room_stmt = select(Room).filter_by(
                tenant_id=tenant_id,
                room_number=reservation["room_number"],
                is_deleted=False
            )
            room = db_session().execute(room_stmt).scalar_one_or_none()

            if not room:
                continue

            ## Idempotency. This demo booking is identified by the room it
            ## occupies, so a second `run_base_seeders` tops the tenant up rather
            ## than stacking an identical booking and burning the next number in
            ## the sequence. The original never checked, so every re-seed added
            ## another reservation.
            already = db_session().execute(
                select(Reservation).filter_by(
                    tenant_id=tenant_id,
                    room_id=room.id,
                    is_deleted=False
                )
            ).scalars().first()

            if already:
                print(
                    f"Demo reservation for room {reservation['room_number']} "
                    f"already exists. Skipping..."
                )
                continue

            # Get or create sequence row (with lock)
            seq_stmt = select(ReservationSequence).filter_by(
                tenant_id=tenant_id,
                prefix_id=prefix.id,
                reservation_year=year,
                reservation_month=month
            ).with_for_update()

            sequence_row = db_session().execute(seq_stmt).scalar_one_or_none()

            if not sequence_row:
                sequence_row = ReservationSequence(
                    tenant_id=tenant_id,
                    prefix_id=prefix.id,
                    reservation_year=year,
                    reservation_month=month,
                    last_sequence=0
                )
                db_session.add(sequence_row)
                db_session.flush()

            # Increment sequence
            sequence_row.last_sequence += 1
            sequence = sequence_row.last_sequence

            # Generate reservation number
            reservation_number = f"{prefix.code}-{year}{month:02d}-{sequence:05d}"

            # Create reservation
            new_reservation = Reservation(
                tenant_id=tenant_id,
                room_id=room.id,
                reservation_number=reservation_number,
                check_in_date=reservation["check_in_date"],
                check_out_date=reservation["check_out_date"],
                total_amount=reservation["total_amount"],
                reservation_status=reservation["reservation_status"],
                created_by=acting_user.id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            db_session.add(new_reservation)

        db_session.commit()
        print("--- Reservations seeded successfully with reservation numbers ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding reservations:", safe_error(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_reservations()
