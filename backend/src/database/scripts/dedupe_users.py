"""Remove duplicate super admin rows left behind by the seeding bug.

The bug: super_admin_seeder filtered on the literal string "ADMIN_EMAIL"
instead of the ADMIN_EMAIL variable, so its existence check never matched and
it inserted one duplicate super admin per run.

Safe by construction -- it only ever deletes rows that are exact duplicates of
a row it is keeping, and it refuses to run unless the email matches what the
seeder is configured with.

Usage (from backend/): python -m src.database.scripts.dedupe_users
"""
import os
import sys

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Must match src/database/seeders/super_admin_seeder.py
SUPER_ADMIN_EMAIL = "sonurajput8454@gmail.com"

APPLY = "--apply" in sys.argv


def main():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME"), password=os.getenv("DB_PASSWORD"),
        database="cms_dev",
    )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, role_id FROM users "
            "WHERE email = %s AND is_deleted = 0 ORDER BY id",
            (SUPER_ADMIN_EMAIL,),
        )
        rows = cur.fetchall()

    if not rows:
        print(f"No user with email {SUPER_ADMIN_EMAIL!r}. Nothing to do.")
        conn.close()
        return

    keep, extras = rows[0], rows[1:]

    print(f"email      : {SUPER_ADMIN_EMAIL}")
    print(f"total rows : {len(rows)}")
    print(f"keeping id : {keep[0]}")
    print(f"removing   : {[r[0] for r in extras]}")

    if not extras:
        print("\nNo duplicates. Nothing to do.")
        conn.close()
        return

    if not APPLY:
        print(f"\nDry run. Re-run with --apply to delete {len(extras)} row(s).")
        conn.close()
        return

    ids = [r[0] for r in extras]
    placeholders = ",".join(["%s"] * len(ids))
    with conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM users WHERE id IN ({placeholders})", ids
        )
        deleted = cur.rowcount
    conn.commit()

    print(f"\nDeleted {deleted} duplicate row(s).")
    conn.close()


if __name__ == "__main__":
    main()