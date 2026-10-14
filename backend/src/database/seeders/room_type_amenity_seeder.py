from sqlalchemy import select
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from datetime import datetime, timezone
from src.api.models import RoomType, RoomAmenity, RoomTypeAmenity
from src.database.session import db_session


# Mapping between room types and room amenities
room_type_amenities_data = {
    "Single": [
        "Air Conditioning",
        "Television",
        "High-Speed Wi-Fi",
        "Work Desk",
        "Wardrobe",
    ],
    "Double": [
        "Air Conditioning",
        "Television",
        "High-Speed Wi-Fi",
        "Work Desk",
        "Wardrobe",
        "Tea & Coffee Maker",
        "Room Service",
    ],
    "Deluxe": [
        "Air Conditioning",
        "Television",
        "High-Speed Wi-Fi",
        "Mini Refrigerator",
        "Tea & Coffee Maker",
        "Private Balcony",
        "Room Service",
        "Hair Dryer",
        "Blackout Curtains",
    ],
    "Suite": [
        "Air Conditioning",
        "Television",
        "High-Speed Wi-Fi",
        "Mini Refrigerator",
        "Tea & Coffee Maker",
        "Private Balcony",
        "Room Service",
        "Hair Dryer",
        "Soundproof Windows",
        "Blackout Curtains",
    ],
}


def seed_room_type_amenities(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for room_type_name, room_amenities_list in room_type_amenities_data.items():

            # Fetch room type. Scoped, so "Deluxe" resolves to this hotel's own
            # room type rather than the first hotel's row of the same name.
            room_type_stmt = select(RoomType).filter_by(
                tenant_id=tenant_id,
                name=room_type_name,
                is_deleted=False
            )
            room_type = db_session().execute(room_type_stmt).scalar_one_or_none()

            if not room_type:
                continue

            for room_amenity_name in room_amenities_list:

                # Fetch amenity
                amenity_stmt = select(RoomAmenity).filter_by(
                    tenant_id=tenant_id,
                    name=room_amenity_name,
                    is_deleted=False
                )
                room_amenity = db_session().execute(amenity_stmt).scalar_one_or_none()

                if not room_amenity:
                    continue

                # Check if mapping already exists
                mapping_stmt = select(RoomTypeAmenity).filter_by(
                    tenant_id=tenant_id,
                    room_type_id=room_type.id,
                    room_amenity_id=room_amenity.id,
                    is_deleted=False
                )
                exists = db_session().execute(mapping_stmt).scalar_one_or_none()

                if not exists:
                    mapping = RoomTypeAmenity(
                        tenant_id=tenant_id,
                        room_type_id=room_type.id,
                        room_amenity_id=room_amenity.id,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    db_session.add(mapping)

        db_session.commit()
        print("--- Room Type Amenities seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding Room Type Amenities:", safe_error(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_room_type_amenities()
