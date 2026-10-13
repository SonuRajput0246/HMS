from sqlalchemy import select
from datetime import datetime, timezone
from src.api.models import RoomType
from src.api.models.room_model import Room
from src.database.session import db_session


rooms_data = [
    {"room_number": "101", "room_type": "Single", "floor_number": 1},
    {"room_number": "102", "room_type": "Single", "floor_number": 1},

    {"room_number": "201", "room_type": "Double", "floor_number": 2},
    {"room_number": "202", "room_type": "Double", "floor_number": 2},

    {"room_number": "301", "room_type": "Deluxe", "floor_number": 3},
    {
        "room_number": "302",
        "room_type": "Deluxe",
        "floor_number": 3,
        "room_status": "maintenance",
        "notes": "Bathroom renovation",
    },
    {"room_number": "401", "room_type": "Suite", "floor_number": 4},
]


def seed_rooms():
    try:
        for data in rooms_data:

            # Fetch room type
            room_type_stmt = select(RoomType).filter_by(
                name=data["room_type"],
                is_deleted=False
            )
            room_type = db_session().execute(room_type_stmt).scalar_one_or_none()

            if not room_type:
                continue

            # Check if room already exists
            stmt = select(Room).filter_by(
                room_number=data["room_number"],
                is_deleted=False
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                room = Room(
                    room_number=data["room_number"],
                    room_type_id=room_type.id,
                    floor_number=data["floor_number"],
                    room_status=data.get("room_status", "available"),
                    notes=data.get("notes"),
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(room)

        db_session.commit()
        print("--- Rooms seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding rooms:", str(e))

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_rooms()
