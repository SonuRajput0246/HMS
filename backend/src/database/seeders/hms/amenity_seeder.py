from sqlalchemy import select
from src.api.models import RoomAmenity
from src.database.session import db_session
from datetime import datetime, timezone

room_amenities_data = [
    {"name":"Air Conditioning","description":"Individually controlled air conditioning for a comfortable stay"},
    {"name":"Television","description":"Flat-screen television with cable and satellite channels"},
    {"name":"High-Speed Wi-Fi","description":"Complimentary high-speed wireless internet access"},
    {"name":"Mini Refrigerator","description":"In-room mini refrigerator for storing beverages and snacks"},
    {"name":"Tea & Coffee Maker","description":"Electric kettle with complimentary tea and coffee supplies"},
    {"name":"Private Balcony","description":"Private balcony with outdoor seating and scenic views"},
    {"name":"Room Service","description":"24-hour in-room dining and housekeeping service"},
    {"name":"Work Desk","description":"Dedicated workspace with desk and ergonomic chair"},
    {"name":"Wardrobe","description":"Spacious wardrobe with hangers and luggage storage"},
    {"name":"Hair Dryer","description":"Wall-mounted hair dryer available in the bathroom"},
    {"name":"Soundproof Windows","description":"Soundproofed windows for a quiet and peaceful stay"},
    {"name":"Blackout Curtains","description":"Blackout curtains to ensure uninterrupted sleep"}
]

def seed_room_amenities():
    try:
        for am in room_amenities_data:
            ## Modern 2.0 syntax: Check if category exists
            stmt = select(RoomAmenity).filter_by(name=am["name"], is_deleted=False)
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                amenity = RoomAmenity(
                    name=am["name"],
                    description=am["description"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)

                )
                db_session.add(amenity)

        db_session.commit()
        print("--- Room amenities seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding room amenities:", str(e))

    finally:
        ## We use .remove() for scoped_sessions to return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_room_amenities()
