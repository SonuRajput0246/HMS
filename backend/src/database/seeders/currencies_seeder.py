"""Seeds currencies from src/database/sql/currencies.sql.

Idempotent: the dump is loaded with INSERT IGNORE, so re-running on a
populated database skips existing rows instead of failing on the primary key.
See sql_statement_loader for why.
"""
from src.database.seeders.sql_statement_loader import run_sql_seeder


def seed_currencies(file_path):
    return run_sql_seeder(
        "Currencies seeder",
        file_path,
        "Currencies seeded successfully!",
    )


if __name__ == "__main__":
    seed_currencies("src/database/sql/currencies.sql")