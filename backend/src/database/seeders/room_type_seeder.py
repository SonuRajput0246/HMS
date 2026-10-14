from sqlalchemy import select
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from src.api.models import RoomType
from datetime import datetime, timezone

room_types_data = [
    {"name":"Single","description":"Single bed room", "max_adults": 1, "max_children": 0, "max_infants": 1, "base_price": 1500, "extra_bed_allowed": False, "extra_bed_price": 0},
    {"name":"Double","description":"Double bed room", "max_adults": 2, "max_children": 1, "max_infants": 1, "base_price": 2500, "extra_bed_allowed": True, "extra_bed_price": 500},
    {"name":"Deluxe","description":"Deluxe room with premium facilities", "max_adults": 2, "max_children": 2, "max_infants": 1, "base_price": 4000, "extra_bed_allowed": True, "extra_bed_price": 800},
    {"name":"Suite","description":"Luxury suite", "max_adults": 4, "max_children": 2, "max_infants": 2, "base_price": 7000, "extra_bed_allowed": True, "extra_bed_price": 1200}
]

def seed_room_types(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for room in room_types_data:
            ## Modern 2.0 syntax: Check if category exists.
            ## Scoped to the hotel: two hotels both sell a "Deluxe" room at their
            ## own price, so the name is only unique inside one hotel.
            stmt = select(RoomType).filter_by(
                tenant_id=tenant_id,
                name=room["name"],
                is_deleted=False
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                room_type = RoomType(
                    tenant_id=tenant_id,
                    name=room["name"],
                    description=room["description"],
                    max_adults=room["max_adults"],
                    max_children=room["max_children"],
                    max_infants=room["max_infants"],
                    base_price=room["base_price"],
                    extra_bed_allowed=room["extra_bed_allowed"],
                    extra_bed_price=room["extra_bed_price"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(room_type)

        db_session.commit()
        print("--- Room Type seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding Room Type:", safe_error(e))
        raise

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_room_types()
