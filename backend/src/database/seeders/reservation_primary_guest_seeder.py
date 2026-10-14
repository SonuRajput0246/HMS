from sqlalchemy import select
from datetime import datetime, timezone
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.api.models.reservation_model import Reservation
from src.api.models.guest_model import Guest
from src.api.models.reservation_primary_guest_model import ReservationPrimaryGuest
from src.database.session import db_session


def seed_reservation_primary_guest(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        # Get latest reservation, this hotel's own. Unscoped, this would attach
        # hotel A's newest booking to hotel B's guest.
        reservation_stmt = (
            select(Reservation)
            .filter_by(tenant_id=tenant_id, is_deleted=False)
            .order_by(Reservation.id.desc())
        )
        reservation = db_session().execute(reservation_stmt).scalars().first()

        if not reservation:
            print("!!! Reservation not found")
            return

        # Fetch guest. Scoped, because the same email exists in every hotel that
        # seeded the demo data.
        guest_stmt = select(Guest).filter_by(
            tenant_id=tenant_id,
            email="rahulsharma@example.com",
            is_deleted=False
        )
        guest = db_session().execute(guest_stmt).scalar_one_or_none()

        if not guest:
            print("!!! Guest not found")
            return

        # Check if already mapped
        stmt = select(ReservationPrimaryGuest).filter_by(
            tenant_id=tenant_id,
            reservation_id=reservation.id
        )
        exists = db_session().execute(stmt).scalar_one_or_none()

        if exists:
            print("!!! Mapping already exists")
            return

        # Create mapping
        new_link = ReservationPrimaryGuest(
            tenant_id=tenant_id,
            reservation_id=reservation.id,
            primary_guest_id=guest.id,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(new_link)

        db_session.commit()
        print("--- Reservation Primary Guest mapped successfully ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error:", safe_error(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_reservation_primary_guest()
