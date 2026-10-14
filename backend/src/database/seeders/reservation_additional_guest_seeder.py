from sqlalchemy import select
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.api.models.reservation_model import Reservation
from src.api.models.additional_guest_model import AdditionalGuest
from src.api.models.reservation_additional_guest_model import ReservationAdditionalGuest
from src.database.session import db_session
from datetime import datetime, timezone

def seed_reservation_additional_guests(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        # Get latest reservation, this hotel's own.
        reservation_stmt = (
            select(Reservation)
            .filter_by(tenant_id=tenant_id, is_deleted=False)
            .order_by(Reservation.id.desc())
        )
        reservation = db_session().execute(reservation_stmt).scalars().first()

        if not reservation:
            print("!!! Reservation not found")
            return

        # Fetch all of this hotel's additional guests
        guest_stmt = select(AdditionalGuest).filter_by(
            tenant_id=tenant_id,
            is_deleted=False
        )
        guests = db_session().execute(guest_stmt).scalars().all()

        if not guests:
            print("!!! Guests not found")
            return

        # Get already mapped guest IDs
        existing_stmt = select(ReservationAdditionalGuest.additional_guest_id).filter_by(
            tenant_id=tenant_id,
            reservation_id=reservation.id
        )
        existing_ids = set(db_session().execute(existing_stmt).scalars().all())

        # Create only new mappings
        new_links = []
        for guest in guests:
            if guest.id not in existing_ids:
                new_links.append(
                    ReservationAdditionalGuest(
                        tenant_id=tenant_id,
                        reservation_id=reservation.id,
                        additional_guest_id=guest.id,
                        created_at=datetime.now(timezone.utc)
                    )
                )

        if new_links:
            db_session.add_all(new_links)
            db_session.commit()
            print(f"--- {len(new_links)} Additional Guests mapped successfully ---")
        else:
            print("--- All guests already mapped ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error:", safe_error(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_reservation_additional_guests()
