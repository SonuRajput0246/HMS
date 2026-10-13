"""Seeds cafe table zones and the tables in them.

Nothing here creates order history -- it is layout only, so a fresh CMS
install opens with a usable floor instead of an empty one. A cafe is free to
rename, reorder or delete every row after this runs.

Idempotent, matched on the natural key (`name` for zones, `table_number` for
tables) rather than on id, so re-running never duplicates and never fights
with rows an admin has edited.

`name` values must satisfy name_field's regex, letters, spaces, apostrophes
and hyphens only -- no digits. That is a person-name validator being applied to
a venue name, which is why nothing here is called "Zone 1".
"""
from datetime import datetime, timezone

from sqlalchemy import select

from src.api.models.cms.table_model import Table
from src.api.models.cms.table_zone_model import TableZone
from src.database.session import db_session


zones_data = [
    {"name": "Main Hall", "display_name": "Main Hall", "display_order": 1,
     "description": "Central dining floor"},
    {"name": "Patio", "display_name": "Patio", "display_order": 2,
     "description": "Covered outdoor seating"},
    {"name": "Balcony", "display_name": "Balcony", "display_order": 3,
     "description": "Upper level, small tables"},
]

## Each entry lists its zone by name. Resolving at seed time rather than
## hardcoding zone ids keeps this correct on a database whose auto-increment
## did not start where the previous install's did.
tables_data = [
    {"zone": "Main Hall", "table_number": "M01", "table_name": "Main One",
     "capacity": 4, "shape": "square", "position_x": 1, "position_y": 1},
    {"zone": "Main Hall", "table_number": "M02", "table_name": "Main Two",
     "capacity": 4, "shape": "round", "position_x": 2, "position_y": 1},
    {"zone": "Main Hall", "table_number": "M03", "table_name": "Main Three",
     "capacity": 6, "shape": "rectangle", "position_x": 3, "position_y": 1},
    {"zone": "Main Hall", "table_number": "M04", "table_name": "Main Four",
     "capacity": 2, "shape": "round", "position_x": 4, "position_y": 1},
    {"zone": "Patio", "table_number": "P01", "table_name": "Patio One",
     "capacity": 2, "shape": "round", "position_x": 1, "position_y": 1},
    {"zone": "Patio", "table_number": "P02", "table_name": "Patio Two",
     "capacity": 4, "shape": "square", "position_x": 2, "position_y": 1},
    {"zone": "Balcony", "table_number": "B01", "table_name": "Balcony One",
     "capacity": 2, "shape": "square", "position_x": 1, "position_y": 1},
]


def _safe(message: str) -> str:
    """Printable on a cp1252 console, unlike a raw MySQL error."""
    return message.encode("ascii", "replace").decode("ascii")


def seed_table_zones():
    """Create the zones. Returns {name: TableZone} for the table seeder."""
    resolved = {}
    created = 0

    for row in zones_data:
        zone = db_session.execute(
            select(TableZone).filter_by(name=row["name"])
        ).scalars().first()

        if zone:
            ## Refresh the mutable fields but leave is_deleted alone: an
            ## admin who deleted a seeded zone should not get it back on the
            ## next deploy.
            zone.display_name = row["display_name"]
            zone.description = row["description"]
            zone.display_order = row["display_order"]
            zone.is_active = True
            zone.updated_at = datetime.now(timezone.utc)
        else:
            zone = TableZone(
                name=row["name"],
                display_name=row["display_name"],
                description=row["description"],
                display_order=row["display_order"],
                is_active=True,
                is_deleted=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(zone)
            created += 1

        resolved[row["name"]] = zone

    db_session.flush()
    print(f"--- Table zones seeded. ({created} created) ---")
    return resolved


def seed_tables(zones_by_name):
    created = 0

    for row in tables_data:
        zone = zones_by_name.get(row["zone"])
        if zone is None:
            raise LookupError(
                f"table_seeder: unknown zone {row['zone']!r}. "
                f"Known: {sorted(zones_by_name)}"
            )

        existing = db_session.execute(
            select(Table).filter_by(table_number=row["table_number"])
        ).scalars().first()

        if existing:
            ## Same rule as zones: an admin's delete is not undone by a deploy.
            existing.table_name = row["table_name"]
            existing.capacity = row["capacity"]
            existing.shape = row["shape"]
            existing.position_x = row["position_x"]
            existing.position_y = row["position_y"]
            existing.zone_id = zone.id
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db_session.add(Table(
                table_number=row["table_number"],
                table_name=row["table_name"],
                capacity=row["capacity"],
                ## Model default, restated: a seeded table must never open
                ## occupied, which is a state an open order owns.
                status="available",
                zone_id=zone.id,
                position_x=row["position_x"],
                position_y=row["position_y"],
                shape=row["shape"],
                is_active=True,
                is_combinable=False,
                is_deleted=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            created += 1

    db_session.flush()
    print(f"--- Tables seeded. ({created} created) ---")


def seed_floor_plan():
    """Zones and tables together, in one transaction."""
    try:
        zones = seed_table_zones()
        seed_tables(zones)
        db_session.commit()
        print("--- Floor plan seeded successfully. ---")

    except Exception as exc:
        db_session.rollback()
        print(f"!!! Floor plan seeder FAILED: {_safe(str(exc))[:300]}")
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_floor_plan()