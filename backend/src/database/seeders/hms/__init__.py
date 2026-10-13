"""HMS seeders.

Bucket: hms -- hotel only

Import a specific seeder directly:

    from src.database.seeders.hms.room_seeder import seed_rooms

`seeders/__init__.py` deliberately imports nothing. Seeder modules open
database sessions at call time, and eagerly importing them here would make
`import src.database.seeders` a side-effecting operation.
"""
