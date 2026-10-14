"""Dynamic booking test: can the *second* hotel use its own booking flows?

Phase 3 made the write guard refuse a row that points at another hotel's user.
Three call sites still named a bare user id -- `created_by=1` on a reservation,
`verified_by=1` on a payment, `role_id=1` on self-registration -- which was fine
while there was one user and becomes a cross-tenant reference the moment a second
hotel exists. The first two are now the authenticated actor. This proves it the
only way that matters: by booking at the second hotel.

    python -m src.database.scripts.tenant_booking_test
    python -m src.database.scripts.tenant_booking_test --keep   # leave the db

It builds a throwaway database (`hms_bookingtest`), seeds the platform, provisions
`acme` (the first hotel) and `globex` (the second), fills globex with the demo
rooms, then, with globex's admin as the acting user, asserts:

  1. A reservation can be created at the second hotel at all. With the old
     `created_by=1` the guard refused it, because user 1 belongs to acme.
  2. It is attributed to the acting user, not to user 1.
  3. CONTROL: a reservation written by hand with `created_by=1` *is* refused --
     the failure the fix removes.
  4. A payment can be recorded, and is verified by the acting user.

The exchange-rate call is stubbed; it hits a public HTTP API that would make this
test network-dependent. Everything else is the real service path.

Exit code is 0 when every check passes and 1 otherwise.
"""
import argparse
import sys
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import scoped_session, sessionmaker

from src.config import get_config

SCRATCH_DB = "hms_bookingtest"

_failures = []
_passes = 0


def check(label, ok, detail=""):
    global _passes
    if ok:
        _passes += 1
        print(f"  PASS  {label}")
    else:
        _failures.append(label)
        print(f"  FAIL  {label}")
        if detail:
            for line in str(detail).splitlines():
                print(f"          {line}")


def build_scratch_database():
    url = make_url(get_config().DATABASE_URL)
    admin = create_engine(url.set(database="mysql"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
        conn.execute(text(
            f"CREATE DATABASE `{SCRATCH_DB}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))

    import src.database.session as session_module
    session_module.engine.dispose()
    scratch = create_engine(url.set(database=SCRATCH_DB), pool_pre_ping=True)
    session_module.engine = scratch
    session_module.session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=scratch
    )
    session_module.db_session = scoped_session(session_module.session_factory)

    import src.api.models  # noqa: F401
    import src.api.events.user_events  # noqa: F401
    import src.api.events.email_otp_events  # noqa: F401
    import src.api.events.role_events  # noqa: F401
    import src.api.events.inventory_events  # noqa: F401
    import src.api.events.room_events  # noqa: F401
    import src.api.events.reservation_events  # noqa: F401
    import src.api.events.guest_events  # noqa: F401
    import src.api.events.payment_events  # noqa: F401
    import src.api.events.tenant_events  # noqa: F401
    import src.api.events.platform_user_events  # noqa: F401

    from src.database.base import Base
    Base.metadata.create_all(scratch)
    return scratch, admin


def drop_scratch_database(scratch, admin):
    from src.database.session import db_session
    db_session.remove()
    scratch.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
    admin.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true",
                        help="leave the scratch database in place")
    args = parser.parse_args()

    scratch = admin = None
    try:
        scratch, admin = build_scratch_database()

        import app as flask_app
        application = flask_app.create_app()
        application.config["TESTING"] = True

        ## The rate lookup is a live HTTP call to a public API; stub it so the
        ## test is deterministic. The class attribute is patched, which is what
        ## PaymentService holds a reference to.
        from src.api.services.exchange_service import ExchangeService
        ExchangeService.get_rate = staticmethod(lambda from_currency, to: Decimal("1"))

        from src.database.session import db_session as db
        from src.database.seeders.run_base_seeders import (
            seed_platform_data,
            seed_tenant_demo_data,
        )
        from src.database.seeders.provision_tenant import provision_tenant

        with application.app_context():
            seed_platform_data()
            acme = provision_tenant("acme", "Acme Hotel", "admin@acme.test", "pw-acme-123")
            globex = provision_tenant("globex", "Globex Hotel", "admin@globex.test", "pw-globex-123")
            acme_id, globex_id = acme.id, globex.id
            ## Rooms live in the demo data, which real provisioning never seeds.
            seed_tenant_demo_data(globex_id)

        print(f"\nprovisioned acme (id={acme_id}) and globex (id={globex_id}), with rooms")

        from flask import g
        from src.api.models import Payment, Reservation, Room, User
        from src.api.services.reservation_service import ReservationService
        from src.database.tenant_context import tenant_context
        from src.database.tenant_enforcement import CrossTenantReferenceError

        stay = {"check_in_date": "2027-06-01", "check_out_date": "2027-06-03",
                "total_adults": 1}

        with application.test_request_context():
            with tenant_context(globex_id):
                globex_admin = db.query(User).filter_by(email="admin@globex.test").first()
                check("globex has an admin", globex_admin is not None)
                check("the admin is not the first user in the database",
                      globex_admin.id != 1, globex_admin.id)

                ## Stand in for what authenticate() sets on g for the request.
                g.current_user = globex_admin

                room = db.query(Room).filter_by(is_deleted=False, is_active=True).first()
                check("globex has a bookable room", room is not None)

                print("\n[1] the second hotel can book")
                service = ReservationService(db)
                result, code = service.create_reservation({"room_id": room.id, **stay})
                check("a reservation is created at the second hotel",
                      isinstance(result, dict) and result.get("status") and code == 201,
                      (code, result))

                reservation_id = (result.get("data") or {}).get("reservation_id") if result.get("status") else None
                reservation = (
                    db.query(Reservation).filter_by(id=reservation_id).first()
                    if reservation_id else None
                )
                check("the reservation is attributed to the acting user",
                      reservation is not None and reservation.created_by == globex_admin.id,
                      (reservation.created_by if reservation else None, globex_admin.id))
                check("it is NOT attributed to user 1",
                      reservation is not None and reservation.created_by != 1,
                      reservation.created_by if reservation else None)

                ## The route commits after create_reservation returns; do the same
                ## here so the control's rollback below cannot take the booking
                ## with it.
                db.commit()

                print("\n[2] control: the old hardcoded value is refused")
                refused = False
                try:
                    db.add(Reservation(
                        room_id=room.id,
                        reservation_number="RES-CONTROL-00001",
                        check_in_date=datetime(2027, 6, 1),
                        check_out_date=datetime(2027, 6, 3),
                        total_amount=Decimal("100"), total_nights=2,
                        reservation_status="created", created_by=1,
                        total_adults=1, total_children=0, total_infants=0,
                    ))
                    db.flush()
                except CrossTenantReferenceError:
                    refused = True
                finally:
                    db.rollback()
                check("a reservation written with created_by=1 is refused for globex", refused)

                print("\n[3] the second hotel can record a payment")
                payment_result, payment_code = service.insert_reservation_payment({
                    "reservation_id": reservation_id,
                    "amount": "1500", "currency": "INR", "payment_method": "cash",
                    "payment_type": "advance", "payment_status": "success",
                })
                check("a payment is recorded at the second hotel",
                      isinstance(payment_result, dict) and payment_result.get("status"),
                      (payment_code, payment_result))

                payment = db.query(Payment).filter_by(reservation_id=reservation_id).first()
                check("the payment is verified by the acting user",
                      payment is not None and payment.verified_by == globex_admin.id,
                      (payment.verified_by if payment else None, globex_admin.id))

        print(f"\n  {_passes} passed, {len(_failures)} failed")
        if not args.keep:
            drop_scratch_database(scratch, admin)
        return 1 if _failures else 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
