"""Common seeders.

Bucket: common -- runs on every instance

Import a specific seeder directly:

    from src.database.seeders.common.currencies_seeder import seed_currencies

`seeders/__init__.py` deliberately imports nothing. Seeder modules open
database sessions at call time, and eagerly importing them here would make
`import src.database.seeders` a side-effecting operation.
"""
