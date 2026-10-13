from datetime import datetime, timezone
from src.database.session import db_session
from src.api.models.additional_guest_model import AdditionalGuest


def seed_additional_guests():
    try:
        guests = [
            AdditionalGuest(
                full_name="Amit Patel",
                gender="male",
                age=30,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            ),
            AdditionalGuest(
                full_name="Sneha Iyer",
                gender="female",
                age=27,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        ]

        db_session.add_all(guests)
        db_session.commit()

        print("--- Additional Guests seeded successfully ---")

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding additional guests:", str(e))

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_additional_guests()