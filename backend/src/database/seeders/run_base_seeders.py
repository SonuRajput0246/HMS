"""Seeding entry point.

Run with `python -m src.database.seeders.run_base_seeders` from backend/.

Seeding is split by ownership, and the split is the whole point now:

  1. Platform data -- countries, states, cities, currencies, enums, units and the
     module tree. These are the product's own rows, seeded once for the whole
     install, and they carry no `tenant_id`.

  2. Tenant data -- everything a single hotel owns. Each of these seeders stamps
     its rows with one tenant and has to be told which one; see `_seeding.py`
     for why that is an error rather than a default.

This module is the local-development bootstrap. It seeds the platform, makes
sure a default tenant exists, fills in that tenant's defaults, and then adds the
sample hotel -- stock, room types, rooms, guests and a reservation -- that makes
the UI worth looking at.

A hotel created for real goes through `provision_tenant.provision_tenant`
instead, which seeds the same defaults but none of the sample data.

Two orderings are load-bearing and easy to break by re-sorting the calls:

  1. Modules seed before roles. `role_seeder` reads the live `modules` table and
     grants permissions only for modules that exist, so seeding roles first
     silently produces roles with no permissions at all.

  2. The tenant's admin user seeds before the demo data. The demo reservation
     references a real `users.id`, and there is no user until the admin exists.
"""
from src.database.seeders.countries_states_cities_seeder import seed_countries_states_cities
from src.database.seeders.currencies_seeder import seed_currencies
from src.database.seeders.enum_seeder import seed_enums
from src.database.seeders.inventory_units_seeder import seed_inventory_units
from src.database.seeders.module_seeder import seed_modules

from src.database.seeders.additional_guest_seeder import seed_additional_guests
from src.database.seeders.amenity_seeder import seed_room_amenities
from src.database.seeders.guest_seeder import seed_guest
from src.database.seeders.inventory_category_seeder import seed_inventory_categories
from src.database.seeders.inventory_seeder import seed_inventories
from src.database.seeders.reservation_additional_guest_seeder import seed_reservation_additional_guests
from src.database.seeders.reservation_primary_guest_seeder import seed_reservation_primary_guest
from src.database.seeders.reservation_seeder import seed_reservations
from src.database.seeders.room_blocks_seeder import seed_room_blocks
from src.database.seeders.room_seeder import seed_rooms
from src.database.seeders.room_type_amenity_seeder import seed_room_type_amenities
from src.database.seeders.room_type_seeder import seed_room_types

from src.database.seeders.provision_tenant import (
    get_or_create_tenant,
    seed_tenant_defaults,
)
from src.database.seeders.super_admin_seeder import seed_super_admin
from src.database.tenant_context import tenant_context


## The hotel a fresh development database gets. Override by passing arguments
## to run_base_seeders().
DEFAULT_TENANT_SLUG = "demo"
DEFAULT_TENANT_NAME = "Demo Hotel"


def seed_platform_data():
    """Product-owned rows. Seeded once per install, and never per tenant."""
    ## Reference data first: enums, currencies, countries and units are inputs
    ## to everything below.
    seed_enums()
    seed_currencies("src/database/sql/currencies.sql")
    seed_countries_states_cities("src/database/sql/countries_states_cities.sql")
    seed_inventory_units()

    ## Modules next, before any role. role_seeder reads the live `modules` table
    ## and grants permissions only for modules that exist, so seeding roles
    ## first silently produces roles with no permissions at all.
    print(">>>>> Seeding modules")
    seed_modules()


def seed_tenant_demo_data(tenant_id: int):
    """The sample hotel: stock, room types, rooms, guests and one reservation.

    Local development only. `provision_tenant` never calls this. Padding a real
    customer's system with another hotel's data is worse than an empty screen,
    because they have to find and delete all of it before the numbers mean
    anything.

    Order is dependency order, not alphabetical: stock before rooms, rooms
    before reservations, and guests before the links that join them.
    """
    with tenant_context(tenant_id):
        seed_inventory_categories(tenant_id)
        seed_inventories(tenant_id)
        seed_room_amenities(tenant_id)
        seed_room_types(tenant_id)
        seed_room_type_amenities(tenant_id)
        seed_rooms(tenant_id)
        seed_room_blocks(tenant_id)      ## Contain Dummy Data
        ## Guests reference the global cities/countries, so they seed
        ## independently of the rooms above.
        seed_guest(tenant_id)
        seed_additional_guests(tenant_id)
        ## Reservations need a room and the RES prefix + sequence.
        seed_reservations(tenant_id)     ## Contain Dummy Data
        seed_reservation_primary_guest(tenant_id)
        seed_reservation_additional_guests(tenant_id)


def run_base_seeders(
    tenant_slug: str = DEFAULT_TENANT_SLUG,
    tenant_name: str = DEFAULT_TENANT_NAME,
    include_demo: bool = True,
):
    """Bootstrap a development install: platform rows, one hotel, sample data."""
    print("Seeding base data")

    ## Shared by every hotel, so it is seeded before any tenant exists.
    seed_platform_data()

    tenant = get_or_create_tenant(tenant_slug, tenant_name)
    ## Take the id as a plain int before anything seeds. Every seeder closes its
    ## session when it finishes, which detaches `tenant`; the id stays valid, the
    ## ORM instance does not.
    tenant_id = tenant.id
    print(f">>>>> Seeding tenant {tenant.slug!r} (id={tenant_id})")

    ## One scope for the whole hotel bootstrap. seed_tenant_defaults and
    ## seed_tenant_demo_data nest their own, which is safe by design -- but
    ## entering it here means the admin user is created inside a tenant scope
    ## too, so nothing in this block can run without one.
    with tenant_context(tenant_id):
        ## Roles, prefixes, sequences, settings, templates, slides.
        seed_tenant_defaults(tenant_id)

        ## The dev credentials are the defaults inside super_admin_seeder;
        ## provisioning passes real ones instead.
        seed_super_admin(tenant_id)

        if include_demo:
            seed_tenant_demo_data(tenant_id)

    print("***** Base seeders executed successfully. *****")


if __name__ == "__main__":
    run_base_seeders()
