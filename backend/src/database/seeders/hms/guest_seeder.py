"""Seeds two demo guests.

Location is stored by NAME, not by id. These rows used to carry literal
foreign keys -- city_id 2715, state_id 22, country_id 101 -- copied out of one
developer's database. That is only ever correct on that one database: a fresh
install assigns different auto-increment values, so the insert dies on a
foreign key constraint and the error points at the guest rather than at the
stale id.

Resolving by name also makes this work against any instance's own database,
which matters now that each instance can have a separate one.

These tables use `name` (not `country_name` / `state_name`) and have no
`is_deleted` column -- they are reference data with an `is_active` flag.
"""
from datetime import date, datetime, timezone

from sqlalchemy import select

from src.api.models.common.city_model import City
from src.api.models.common.country_model import Country
from src.api.models.common.state_model import State
from src.api.models.hms.guest_model import Guest
from src.database.session import db_session


guests_data = [
    {
        "first_name": "Rahul",
        "last_name": "Sharma",
        "gender": "male",
        "date_of_birth": date(1992, 5, 14),
        "email": "rahulsharma@example.com",
        "phone_number": "9876543210",
        "address": "MG Road",
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "id_type": "aadhar",
        "id_number": "123412341234",
        "nationality": "India",
        "vip_status": False,
        "blacklist_status": False,
        "notes": "Regular guest",
        "is_active": True,
    },
    {
        "first_name": "Priya",
        "last_name": "Verma",
        "gender": "female",
        "date_of_birth": date(1995, 8, 22),
        "email": "priya.verma@example.com",
        "phone_number": "9988776655",
        "address": "Thane East",
        "city": "Thane",
        "state": "Maharashtra",
        "country": "India",
        "id_type": "passport",
        "id_number": "P9876543",
        "nationality": "India",
        "vip_status": True,
        "blacklist_status": False,
        "notes": "VIP Guest",
        "is_active": True,
    },
]

NAME_KEYS = ("city", "state", "country", "nationality")


def _resolve_location_ids(guest: dict) -> dict:
    """Look up the foreign keys for one guest's location names.

    Raises when a name is unknown rather than inserting NULL. A NULL passes the
    FK constraint but produces a guest with no location, which silently breaks
    every report that groups by country.
    """
    country = db_session.execute(
        select(Country).where(Country.name == guest["country"])
    ).scalars().first()

    state = db_session.execute(
        select(State).where(
            State.name == guest["state"],
            State.country_id == (country.id if country else -1),
        )
    ).scalars().first()

    city = db_session.execute(
        select(City).where(
            City.name == guest["city"],
            City.state_id == (state.id if state else -1),
        )
    ).scalars().first()

    nationality = db_session.execute(
        select(Country).where(Country.name == guest["nationality"])
    ).scalars().first()

    missing = [
        label
        for label, value in (
            ("country", country), ("state", state),
            ("city", city), ("nationality", nationality),
        )
        if value is None
    ]
    if missing:
        raise LookupError(
            f"guest_seeder: {guest['email']} references unknown "
            f"{', '.join(missing)}. Run countries_states_cities_seeder first."
        )

    return {
        "country_id": country.id,
        "state_id": state.id,
        "city_id": city.id,
        "nationality_id": nationality.id,
    }


def seed_guest():
    try:
        for guest in guests_data:
            existing = db_session.execute(
                select(Guest).filter_by(
                    email=guest["email"], is_deleted=False
                )
            ).scalar_one_or_none()

            if existing:
                continue

            # Swap the names for their resolved ids, and drop the name keys so
            # they are never passed to the ORM constructor.
            payload = {k: v for k, v in guest.items() if k not in NAME_KEYS}
            payload.update(_resolve_location_ids(guest))

            db_session.add(Guest(
                **payload,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))

        db_session.commit()
        print("--- Guest seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        # Raise rather than print-and-return: the "additional guests" seeder
        # that runs next used to fail on a missing guest, pointing at the
        # wrong seeder entirely.
        print(f"!!! Guest seeder FAILED: "
              f"{str(e).encode('ascii', 'replace').decode('ascii')[:300]}")
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_guest()