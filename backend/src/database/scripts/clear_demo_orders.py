"""Removes the demo orders created by order_seeder, and undoes what they did.

Scoped to the SEED_MARKER prefix in cms_orders.notes, never a truncate. This can
run against a database that also holds real tickets.

Run it with --apply. The default is a dry run, matching prune_modules.py.

The visit-banking reversal is the part that is easy to miss. order_seeder calls
Customer.record_visit() for every completed order it creates, because
CMSOrder.complete() does the same and the customer report's leaderboard filters
on total_visits > 0. Deleting the demo orders without walking those counters
back leaves every customer permanently inflated: a regular who made 4 demo
purchases keeps showing 4 visits and the spend that came with them forever, and
re-seeding adds another 4 on top. The counters are recomputed from the
non-demo orders rather than decremented, so the result is correct whether the
drift happened once or several times.

Usage:
    python -m src.database.scripts.clear_demo_orders          # dry run
    python -m src.database.scripts.clear_demo_orders --apply
"""
import argparse
import os
import sys
from decimal import Decimal

import pymysql
from dotenv import load_dotenv

load_dotenv()

from src.database.seeders.cms.order_seeder import SEED_MARKER  # noqa: E402

## Above this the marker has matched something other than seeded demo data and
## deleting on that basis would be reckless.
MAX_ROWS = 500


def connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME"), password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="actually delete; without this nothing is written")
    args = parser.parse_args()

    conn = connect()
    marker = f"{SEED_MARKER}%"
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cms_orders WHERE notes LIKE %s", (marker,))
        order_count = cur.fetchone()[0]

        if order_count == 0:
            print("No demo orders found. Nothing to do.")
            conn.close()
            return 0

        if order_count > MAX_ROWS:
            print(
                f"Refusing: {order_count} orders match {SEED_MARKER!r}, more than "
                f"order_seeder creates (max {MAX_ROWS}). The marker may be "
                "matching real data."
            )
            conn.close()
            return 1

        # What each customer's counters contributed, so it can be taken back.
        cur.execute(
            """
            SELECT c.id, c.name, c.total_visits, c.total_spent, c.loyalty_points,
                   COUNT(o.id) AS demo_orders,
                   COALESCE(SUM(o.total_amount), 0) AS demo_spend
              FROM cms_orders o
              JOIN customers c ON c.id = o.customer_id
             WHERE o.notes LIKE %s AND o.status = 'COMPLETED'
             GROUP BY c.id, c.name, c.total_visits, c.total_spent, c.loyalty_points
            """,
            (marker,),
        )
        customers = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM cms_order_items WHERE order_id IN "
                    "(SELECT id FROM cms_orders WHERE notes LIKE %s)", (marker,))
        item_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cms_payments WHERE order_id IN "
                    "(SELECT id FROM cms_orders WHERE notes LIKE %s)", (marker,))
        payment_count = cur.fetchone()[0]

        print(f"Demo orders matching {SEED_MARKER!r}: {order_count}")
        print(f"  order items: {item_count}   payments: {payment_count}")
        print("Customer counters to be recomputed:")
        for cid, name, visits, spent, points, n, demo_spend in customers:
            print(f"  {name:<18} visits={visits} spent={spent} points={points}"
                  f"   (from {n} demo orders worth {demo_spend})")

        if not args.apply:
            print("\nDry run. Nothing written. Re-run with --apply to delete.")
            conn.close()
            return 0

        # Children go with the parent via ON DELETE CASCADE on cms_order_items
        # and cms_payments. The counters are recomputed from what remains
        # rather than decremented, so repeated drift still lands correct.
        cur.execute("DELETE FROM cms_orders WHERE notes LIKE %s", (marker,))
        deleted = cur.rowcount

        for cid, _name, _visits, _spent, _points, _n, _demo_spend in customers:
            cur.execute(
                """
                SELECT COUNT(*) AS visits, COALESCE(SUM(total_amount), 0) AS spend
                  FROM cms_orders
                 WHERE customer_id = %s AND is_deleted = 0 AND status = 'COMPLETED'
                """,
                (cid,),
            )
            visits, spend = cur.fetchone()
            # Loyalty is 1 point per 10 units, matching Customer.record_visit.
            points = int(Decimal(str(spend)) / 10)
            cur.execute(
                "UPDATE customers SET total_visits=%s, total_spent=%s, "
                "loyalty_points=%s WHERE id=%s",
                (visits, Decimal(str(spend)), points, cid),
            )

        # Tables the demo tickets sat on must go back to serviceable, or the
        # floor screen shows permanently occupied tables with no open order.
        cur.execute(
            "UPDATE tables t SET t.status='available' WHERE t.is_deleted=0 "
            "AND t.status='occupied' AND NOT EXISTS ("
            "  SELECT 1 FROM cms_orders o WHERE o.table_id = t.id"
            "    AND o.is_deleted = 0"
            "    AND o.status IN ('PENDING','CONFIRMED','PREPARING','READY','SERVED')"
            ")"
        )
        freed = cur.rowcount
        conn.commit()

        # The cascade is relied on, so confirm there is nothing orphaned rather
        # than assuming it.
        cur.execute("SELECT COUNT(*) FROM cms_order_items WHERE order_id NOT IN "
                    "(SELECT id FROM cms_orders)")
        orphans = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cms_payments WHERE order_id NOT IN "
                    "(SELECT id FROM cms_orders)")
        orphan_payments = cur.fetchone()[0]

    conn.close()
    print(f"\nDeleted {deleted} demo orders, recomputed {len(customers)} customer "
          f"counters, freed {freed} tables.")
    print(f"Orphans after delete: items={orphans} payments={orphan_payments}")
    return 0 if orphans == 0 and orphan_payments == 0 else 1


if __name__ == "__main__":
    sys.exit(main())