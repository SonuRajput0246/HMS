"""Remove modules that belong to a different instance than the database holds.

Running the HMS seeders against a CMS database (or vice versa) inserts the
other instance's modules into the shared `modules` table. Ids then collide and
role_seeder grants permissions against a tree containing both products.

This script keeps only the modules the configured instance declares. It
reports what it would delete and requires --apply.

Usage (from backend/): python -m src.database.scripts.prune_modules [--apply]

Everything is inside main() behind a __main__ guard on purpose. At module
level this file touched a live database and called SystemExit, so merely
importing it -- which any tooling that walks the package will do -- mutated
data and aborted the importing process.
"""
import os
import re
import sys

import pymysql
from dotenv import load_dotenv

SEEDER = {
    "CMS": "src/database/seeders/cms/module_seeder.py",
    "HMS": "src/database/seeders/hms/module_seeder.py",
}


def _connect(dbname=None):
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        database=dbname,
    )


def main():
    load_dotenv()

    instance = (os.getenv("INSTANCE_TYPE") or "").strip().upper()
    if instance not in SEEDER:
        raise SystemExit(
            f"INSTANCE_TYPE must be CMS or HMS, got {instance!r}"
        )

    with open(SEEDER[instance], encoding="utf-8") as fh:
        keep = {n for _i, n in re.findall(
            r'"id":\s*(\d+),\s*\n\s*"module_name":\s*"(\w+)"', fh.read()
        )}

    from src.config import get_config
    dbname = (get_config().DATABASE_URL or "").rsplit("/", 1)[-1].split("?")[0]

    with _connect(dbname).cursor() as cur:
        cur.execute("SELECT id, module_name FROM modules WHERE is_deleted=0")
        present = cur.fetchall()

    extra = [(i, n) for i, n in present if n not in keep]

    print(f"instance : {instance}")
    print(f"database : {dbname}")
    print(f"expected : {len(keep)} modules")
    print(f"present  : {len(present)} modules")
    print()
    print(f"belongs to {instance}:")
    for i, n in sorted(present):
        if n in keep:
            print(f"    id={i:<4} {n}")

    if not extra:
        print("\nNothing to prune.")
        return

    print(f"\nBELONGS TO THE OTHER INSTANCE ({len(extra)}):")
    for i, n in sorted(extra):
        print(f"    id={i:<4} {n}")

    if "--apply" not in sys.argv:
        print(f"\nDry run. Re-run with --apply to delete {len(extra)} row(s).")
        return

    ids = [i for i, _ in extra]
    conn = _connect(dbname)
    with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(ids))
        # role_module_access rows referencing these cascade via FK.
        cur.execute(f"DELETE FROM modules WHERE id IN ({placeholders})", ids)
        deleted = cur.rowcount
    conn.commit()
    conn.close()

    print(f"\nDeleted {deleted} foreign module row(s).")
    print("Re-run the seeders to restore this instance's role permissions.")


if __name__ == "__main__":
    main()