"""Seeds a few CMS customers.

Layout data (floor plan) is separate; this is people. A cafe opens with an
empty customer book otherwise, and every screen that references a customer --
POS, orders, the customer report -- starts blank.

No order history is created. Loyalty points, visit counts and spend totals are
all derived from orders, so a seeded customer starts at zero; the columns are
left to the service so it owns how they are maintained.

Idempotent, matched on `phone`, which the service already treats as a
customer's identity at the till.

Phones are deliberately fictional. These rows land in a dev database today, but
a seeder is exactly the kind of file that gets pointed at production, and real
numbers would then be real people's.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from src.api.models.cms.customer_model import Customer
from src.api.services.common.document_sequence_service import DocumentSequenceService
from src.database.session import db_session


customers_data = [
    {
        "name": "Aarti Sharma",
        "phone": "9800000001",
        "email": "aarti.sharma@example.com",
        "address": "12 Residency Road",
        "dietary_notes": "Vegetarian",
        "is_vip": True,
    },
    {
        "name": "Rohit Menon",
        "phone": "9800000002",
        "email": "rohit.menon@example.com",
        "address": "4 MG Road",
        "dietary_notes": "No shellfish",
        "is_vip": False,
    },
    {
        "name": "Fatima Sheikh",
        "phone": "9800000003",
        "email": "fatima.sheikh@example.com",
        "address": "78 Linking Road",
        "dietary_notes": "Halal",
        "is_vip": False,
    },
]


def seed_customers():
    created = 0
    ## Same generator the API uses. customer_code is NOT NULL with no default,
    ## so a hand-written code would either fail the insert or collide with the
    ## sequence -- DocumentSequenceService owns that format.
    sequence = DocumentSequenceService(db_session)

    for row in customers_data:
        existing = db_session.execute(
            select(Customer).filter_by(phone=row["phone"])
        ).scalars().first()

        if existing:
            ## Refresh the descriptive fields, but leave is_deleted alone: an
            ## admin who removed a seeded customer should not get them back on
            ## the next deploy.
            existing.name = row["name"]
            existing.email = row["email"]
            existing.address = row["address"]
            existing.dietary_notes = row["dietary_notes"]
            existing.is_vip = row["is_vip"]
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db_session.add(Customer(
                customer_code=sequence.generate("customer"),
                name=row["name"],
                phone=row["phone"],
                email=row["email"],
                address=row["address"],
                dietary_notes=row["dietary_notes"],
                is_vip=row["is_vip"],
                is_active=True,
                is_deleted=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            created += 1

    db_session.flush()
    print(f"--- Customers seeded. ({created} created) ---")


def seed_cms_customers():
    """Transaction wrapper, matching the other CMS seeders."""
    try:
        seed_customers()
        db_session.commit()
        print("--- Customers seeded successfully. ---")

    except Exception as exc:
        db_session.rollback()
        print("!!! Customer seeder FAILED: "
              + str(exc).encode("ascii", "replace").decode("ascii")[:300])
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_cms_customers()