"""Base seeding entry point.

Run with `python -m src.database.seeders.run_base_seeders` from backend/.

Seeding is split by bucket, mirroring src/api. `common/` seeders run on every
instance; `hms/` and `cms/` seeders run only for the matching INSTANCE_TYPE.
This is the same switch app.py uses to register blueprints, so the module tree
seeded into `modules` matches the endpoints that actually exist.

Two ordering constraints are load-bearing:

  1. Modules seed before roles. role_seeder reads the live `modules` table and
     grants permissions only for modules that exist, so seeding roles first
     silently produces roles with no permissions.

  2. Inventory seeds before rooms/reservations. The room and reservation seeders
     reference inventory ids.
"""
from src.config import get_config, InstanceType

## Resolve config before importing any seeder: seeder modules read config at
## import time, and INSTANCE_TYPE validation should fail before a session is
## opened rather than halfway through the run.
config = get_config()

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

from src.database.seeders.cms.customer_seeder import seed_cms_customers
from src.database.seeders.cms.floor_plan_seeder import seed_floor_plan
from src.database.seeders.cms.module_seeder import seed_modules_cms
from src.database.seeders.cms.recipe_category_seeder import seed_recipe_categories
from src.database.seeders.cms.recipe_seeder import seed_cms_recipes
from src.database.seeders.cms.order_seeder import seed_cms_orders


## Reference data every instance needs, and that instance data depends on.
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


def run_cms_seeders():
    print(">>>>> Seeding CMS domain data")
    ## Modules are NOT seeded here -- run_base_seeders() does that in the gate
    ## above, before roles, because role_seeder resolves permissions against
    ## the live modules table.
    seed_recipe_categories()
    ## Floor plan before customers: the customer model has a
    ## preferred_table_id, and orders reference both.
    seed_floor_plan()
    seed_cms_customers()
    ## Recipes last: they resolve ingredient lines against inventory and
    ## categories by name, so both must already exist.
    seed_cms_recipes()
    ## Orders after everything they reference. Reports, the dashboard and the
    ## POS summary all read cms_orders, so this is what turns those screens
    ## from well-formed empty payloads into readable ones.
    seed_cms_orders()


def run_base_seeders():
    instance_type = config.INSTANCE_TYPE
    print(f"Seeding for instance: {instance_type}")

    ## Reference data first: enums, currencies, countries and stock are inputs
    ## to everything below.
    seed_reference_data()

    ## Modules next, before roles. role_seeder reads the live `modules` table
    ## and grants permissions only for modules that exist, so seeding roles
    ## first silently produces roles with no permissions at all. The module
    ## tree is instance-specific, so this has to run before the shared
    ## role/super-admin step below.
    print(f">>>>> Seeding modules for {instance_type}")
    if instance_type == InstanceType.HMS:
        seed_modules_hms()
    elif instance_type == InstanceType.CMS:
        seed_modules_cms()
    else:
        ## BaseConfig already rejects a bad value at import, so reaching this is
        ## a programming error rather than bad config.
        raise ValueError(f"Unknown instance type: {instance_type}")

    ## Now that modules exist, roles can resolve their permissions.
    seed_roles()
    seed_super_admin()

    ## Remaining shared tables, then the instance's own domain data.

    ## Previously this block ran every hotel seeder regardless of instance, so a
    ## cafe deployment got rooms, reservations and guests it can never display,
    ## and its module-access tree was seeded from the hotel list. Now each
    ## branch matches the endpoints app.py actually registers.
    if instance_type == InstanceType.HMS:
        run_hms_seeders()
    else:
        run_cms_seeders()

    print("***** Base seeders executed successfully. *****")


if __name__ == "__main__":
    run_base_seeders()