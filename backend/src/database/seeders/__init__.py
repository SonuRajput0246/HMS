"""Database seeders.

Import a specific seeder directly:

    from src.database.seeders.currencies_seeder import seed_currencies

Or run the whole development set in order:

    python -m src.database.seeders.run_base_seeders

Seeders are split into two kinds, and the distinction matters:

  * Platform seeders (countries/states/cities, currencies, enums, inventory
    units, modules) write product-owned reference rows that are shared by every
    hotel and carry no `tenant_id`.

  * Tenant seeders write rows that belong to one hotel. Each takes a
    `tenant_id` and refuses to run without one -- pass it explicitly, or run
    inside `src.database.tenant_context.tenant_context(...)`.

To create a new hotel and its defaults:

    from src.database.seeders.provision_tenant import provision_tenant

This module deliberately imports nothing. Seeder modules open database sessions
at call time, and eagerly importing them here would make
`import src.database.seeders` a side-effecting operation.
"""
