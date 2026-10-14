from datetime import timedelta
from sqlalchemy import select
from datetime import datetime, timezone
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.api.models import Room
from src.api.models.room_blocks_model import RoomBlocks
from src.database.session import db_session


room_blocks_data = [
    {
        "room_number": "401",
        "start_date": datetime.now(),
        "end_date": datetime.now() + timedelta(days=3),
        "blocked_reason": "Renovation work",
    }
]


def seed_room_blocks(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for block in room_blocks_data:

            # Fetch room. Scoped, so room 401 is this hotel's 401.
            room_stmt = select(Room).filter_by(
                tenant_id=tenant_id,
                room_number=block["room_number"],
                is_deleted=False
            )
            room = db_session().execute(room_stmt).scalar_one_or_none()

            if not room:
                continue

            # Check overlapping block existence
            stmt = select(RoomBlocks).filter_by(
                tenant_id=tenant_id,
                room_id=room.id,
                is_deleted=False
            )
            exists = db_session().execute(stmt).scalar_one_or_none()

            if not exists:
                room_block = RoomBlocks(
                    tenant_id=tenant_id,
                    room_id=room.id,
                    start_date=block["start_date"],
                    end_date=block["end_date"],
                    blocked_reason=block["blocked_reason"],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(room_block)

        db_session.commit()
        print("--- Room Blocks seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding room blocks:", safe_error(e))
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_room_blocks()
