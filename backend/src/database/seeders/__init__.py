"""Database seeders.

Import a specific seeder directly:

    from src.database.seeders.currencies_seeder import seed_currencies

Or run the whole base set in order:

    python -m src.database.seeders.run_base_seeders

This module deliberately imports nothing. Seeder modules open database sessions
at call time, and eagerly importing them here would make
`import src.database.seeders` a side-effecting operation.
"""