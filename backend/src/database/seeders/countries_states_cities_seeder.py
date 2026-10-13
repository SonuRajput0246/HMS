"""Seeds countries / states / cities from
src/database/sql/countries_states_cities.sql.

The dump is a third-party export and does not satisfy this schema's
constraints. Two distinct problems, both of which abort a plain INSERT:

  - repeated (state_id, name) pairs, rejected by uq_city_state_name
  - cities whose state_id has no matching row in `states`

INSERT IGNORE demotes both to warnings, so the bad rows are skipped and
everything else loads. Without it a single bad row in a 5000-row VALUES list
discards all 5000 -- which is why a fresh install previously ended up with
zero countries, states and cities while the seeder still printed success.

Skipping is the right trade here: these are reference rows, not user data.
"""
from sqlalchemy import text

from src.database.seeders.sql_statement_loader import run_sql_seeder
from src.database.session import db_session


def seed_countries_states_cities(file_path):
    return run_sql_seeder(
        "Countries/states/cities seeder",
        file_path,
        "Countries, States & Cities seeded successfully!",
    )


def count_rows() -> dict:
    """Row counts, so a partial load is visible rather than inferred."""
    return {
        table: db_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in ("countries", "states", "cities")
    }


if __name__ == "__main__":
    seed_countries_states_cities("src/database/sql/countries_states_cities.sql")