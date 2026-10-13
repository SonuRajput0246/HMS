"""Base seeding entry point.

Run with `python -m src.database.seeders.run_base_seeders` from backend/.

Seeding is split by bucket, mirroring src/api: `common/` seeders populate
shared infrastructure, `hms/` seeders populate the hotel domain.

Two ordering constraints are load-bearing:

  1. Modules seed before roles. role_seeder reads the live `modules` table and
     grants permissions only for modules that exist, so seeding roles first
     silently produces roles with no permissions.

  2. Inventory seeds before rooms/reservations. The room and reservation seeders
     reference inventory ids.
"""
from src.database.seeders.common.countries_states_cities_seeder import seed_countries_states_cities
from src.database.seeders.common.currencies_seeder import seed_currencies
from src.database.seeders.common.enum_seeder import seed_enums
from src.database.seeders.common.inventory_category_seeder import seed_inventory_categories
from src.database.seeders.common.inventory_seeder import seed_inventories
from src.database.seeders.common.inventory_units_seeder import seed_inventory_units
from src.database.seeders.common.login_slider_seeder import seed_login_sliders
from src.database.seeders.common.prefixes_seeder import seed_prefixes
from src.database.seeders.common.role_seeder import seed_roles
from src.database.seeders.common.super_admin_seeder import seed_super_admin
from src.database.seeders.common.system_setting_seeder import seed_system_settings
from src.database.seeders.common.template_seeder import seed_templates

from src.database.seeders.hms.additional_guest_seeder import seed_additional_guests
from src.database.seeders.hms.amenity_seeder import seed_room_amenities
from src.database.seeders.hms.guest_seeder import seed_guest
from src.database.seeders.hms.module_seeder import seed_modules_hms
from src.database.seeders.hms.reservation_additional_guest_seeder import seed_reservation_additional_guests
from src.database.seeders.hms.reservation_primary_guest_seeder import seed_reservation_primary_guest
from src.database.seeders.hms.reservation_seeder import seed_reservations
from src.database.seeders.hms.reservation_sequence_seeder import seed_reservation_sequences
from src.database.seeders.hms.room_blocks_seeder import seed_room_blocks
from src.database.seeders.hms.room_seeder import seed_rooms
from src.database.seeders.hms.room_type_amenity_seeder import seed_room_type_amenities
from src.database.seeders.hms.room_type_seeder import seed_room_types


## Reference data every deployment needs, and that HMS domain data depends on.
def seed_reference_data():
    seed_login_sliders()
    seed_enums()
    seed_templates()
    seed_system_settings()
    seed_currencies("src/database/sql/currencies.sql")
    seed_countries_states_cities("src/database/sql/countries_states_cities.sql")
    seed_prefixes()
    seed_inventory_units()
    seed_inventory_categories()
    seed_inventories()


def run_hms_seeders():
    print(">>>>> Seeding HMS domain data")
    seed_room_amenities()
    seed_room_types()
    seed_room_type_amenities()
    seed_rooms()
    seed_room_blocks()      ## Contain Dummy Data
    seed_reservation_sequences()
    seed_reservations()     ## Contain Dummy Data
    seed_guest()
    seed_additional_guests()
    seed_reservation_primary_guest()
    seed_reservation_additional_guests()


def run_base_seeders():
    print("Seeding base data")

    ## Reference data first: enums, currencies, countries and stock are inputs
    ## to everything below.
    seed_reference_data()

    ## Modules next, before roles. role_seeder reads the live `modules` table
    ## and grants permissions only for modules that exist, so seeding roles
    ## first silently produces roles with no permissions at all.
    print(">>>>> Seeding modules")
    seed_modules_hms()

    ## Now that modules exist, roles can resolve their permissions.
    seed_roles()
    seed_super_admin()

    ## Remaining shared tables, then the hotel domain data.
    run_hms_seeders()

    print("***** Base seeders executed successfully. *****")


if __name__ == "__main__":
    run_base_seeders()