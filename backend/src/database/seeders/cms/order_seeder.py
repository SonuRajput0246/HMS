"""Seeds CMS order history so reports, dashboard and KDS have something to read.

Every one of the six report endpoints, the POS summary tile and the dashboard
charts read `cms_orders`. With no orders they all return well-formed empty
payloads, which looks like a working screen and is not one: sales-summary
reports 0.00 over a period that never had a customer in it, and the kitchen
performance average divides by nothing. Seeded rows are the only way to tell
those screens apart from a genuine zero.

What the seed deliberately produces, because each one exercises a different
report:

  * completed orders across ~14 trading days at varying hours, so the daily
    trend and the hourly buckets both have more than one column
  * a spread of order types and payment methods, for the breakdown panels
  * orders linked to a customer, for the customer report and the loyalty
    counter
  * voided lines (is_deleted + prep_status=voided), which the void report
    reads -- it filters on BOTH, so a line needs both set to appear
  * cancelled orders, which the void report counts on a separate channel and
    folds into `combined_loss`
  * ready items with prep_started_at/prep_completed_at, the only rows the
    kitchen performance averages consider
  * in-flight orders (pending/confirmed/preparing) so the KDS and the open
    table tiles have live tickets

Two conventions the rest of the system depends on:

  - Timestamps are stored naive UTC. They are generated here as Asia/Kolkata
    wall-clock and converted, because a report buckets by business-local hour.
    Writing naive local time straight in would shift every bucket by 5h30m
    and move dinner service into the small hours.
  - order_number comes from DocumentSequenceService, the same generator the API
    uses. A hand-written number either collides on the unique index or drifts
    from the sequence the till will hand out next.

Stock is NOT decremented. Historical orders are demo history; deducting
inventory from them would under-count a cafe's actual stock, and the recipe
cost on the order line is copied from the recipe at pricing time rather than
recomputed.

Idempotent: every row carries SEED_MARKER in `notes`, and the seeder refuses to
run twice. Demo orders are therefore visible as such in the orders list, which
is also how you tell them apart from real tickets.
"""
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from src.api.models.common.inventory_model import Inventory
from src.api.models.common.user_model import User
from src.api.models.cms.customer_model import Customer
from src.api.models.cms.order_model import (
    PREP_PENDING,
    PREP_PREPARING,
    PREP_READY,
    PREP_VOIDED,
    CMSOrder,
    CMSOrderItem,
    CMSPayment,
    OrderStatusEnum,
    OrderTypeEnum,
    PaymentMethodEnum,
    PaymentStatusEnum,
)
from src.api.models.cms.recipe_model import Recipe
from src.api.models.cms.table_model import Table
from src.api.services.common.document_sequence_service import DocumentSequenceService
from src.api.utils.datetime_helper import business_timezone
from src.database.session import db_session


## Notes marker. Doubles as the idempotency guard and as the label an operator
## sees in the orders list, which is the only way to tell demo rows apart.
SEED_MARKER = "[demo]"

HISTORY_DAYS = 14

## Service peaks in Asia/Kolkata local time. Covering both is what gives the
## hourly chart a lunch column and a dinner column.
SERVICE_HOURS = [
    8, 9,
    12, 12, 13, 13, 14,
    16,
    19, 19, 20, 20, 20, 21, 21,
]

ORDER_TYPES = [
    OrderTypeEnum.DINE_IN.value,
    OrderTypeEnum.DINE_IN.value,
    OrderTypeEnum.DINE_IN.value,
    OrderTypeEnum.TAKEAWAY.value,
    OrderTypeEnum.TAKEAWAY.value,
    OrderTypeEnum.DELIVERY.value,
]

PAYMENT_METHODS = [
    PaymentMethodEnum.CASH.value,
    PaymentMethodEnum.CARD.value,
    PaymentMethodEnum.UPI.value,
    PaymentMethodEnum.UPI.value,
    PaymentMethodEnum.WALLET.value,
    PaymentMethodEnum.SPLIT.value,
]

## Kitchen has to clear these inside a time that looks plausible, otherwise
## the average prep time in the report reads as a broken kitchen.
PREP_MINUTES_RANGE = (6, 24)

DINE_IN_TABLES = None  # resolved at runtime from the floor plan


def _safe(message: str) -> str:
    """ASCII-fold a message.

    Windows console stdout is cp1252. print() of a MySQL message carrying
    accented text raises UnicodeEncodeError while handling the original error,
    which hides the real failure.
    """
    return message.encode("ascii", "replace").decode("ascii")


def _local_to_utc_naive(day, hour, minute=0):
    """Wall-clock time in the trading timezone -> naive UTC for storage.

    Reports bucket by business-local hour, so a naive local timestamp written
    straight to the column shifts every bucket by the UTC offset.
    """
    tz = business_timezone()
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _already_seeded() -> bool:
    return db_session.execute(
        select(CMSOrder.id).where(CMSOrder.notes.like(f"{SEED_MARKER}%")).limit(1)
    ).first() is not None


def _load_recipes():
    return db_session.execute(
        select(Recipe).filter(
            Recipe.is_deleted == False, Recipe.is_active == True
        ).order_by(Recipe.id)
    ).scalars().all()


def _load_tables():
    return db_session.execute(
        select(Table).filter(Table.is_deleted == False).order_by(Table.id)
    ).scalars().all()


def _load_customers():
    return db_session.execute(
        select(Customer).filter(Customer.is_deleted == False).order_by(Customer.id)
    ).scalars().all()


def _load_user() -> User:
    """Seeded orders need a created_by. Prefer the super admin, fall back to
    any active user -- an order with a null actor is unattributable in reports.
    """
    user = db_session.execute(
        select(User).filter(
            User.is_deleted == False, User.is_active == True
        ).order_by(User.id)
    ).scalars().first()
    if user is None:
        raise LookupError(
            "order_seeder: no active user. Run super_admin_seeder first -- "
            "cms_orders.created_by is NOT NULL."
        )
    return user


def _build_items(order, recipe_choices, rng, prep_state, prep_window, min_lines=1):
    """Attach 1-4 lines drawn from the recipe list.

    prep_state is the status every line gets; prep_window is when the kitchen
    started and finished them. Lines carry a copy of the recipe's station, which
    is what the per-station kitchen breakdown groups on.

    min_lines is raised to 2 by the caller for orders it intends to void,
    because _void_one_line refuses to take the last line off a ticket.
    """
    count = rng.randint(min_lines, 4)
    chosen = rng.sample(recipe_choices, min(count, len(recipe_choices)))
    started, finished = prep_window

    for recipe in chosen:
        qty = Decimal(str(rng.choice([1, 1, 1, 2, 2, 3])))
        line = CMSOrderItem(
            order_id=order.id,
            item_type="recipe",
            item_id=recipe.id,
            ## Denormalised at ring-up time: an order line must not retitle
            ## itself because a recipe was renamed afterwards.
            item_name=recipe.display_name or recipe.name,
            quantity=qty,
            unit_price=Decimal(str(recipe.selling_price)),
            station=recipe.station,
            spice_level=recipe.default_spice_level,
            prep_status=prep_state,
            is_deleted=False,
            created_at=order.ordered_at,
            updated_at=order.ordered_at,
        )
        if prep_state == PREP_READY:
            line.prep_started_at = started
            line.prep_completed_at = finished
        ## Appended to the relationship rather than added with order_id set:
        ## CMSOrder.calculate_totals sums `self.items`, the loaded collection.
        ## A line added by foreign key alone is pending in the session and the
        ## parent's collection can stay empty, which silently totals the order
        ## at 0.00 -- and a 0.00 payment trips ck_cms_payment_amount_positive.
        order.items.append(line)


def _void_one_line(order, rng, user_id, when):
    """Void a single line the way the cashier path does.

    OrderService.void_item sets is_deleted AND prep_status; the void report
    filters on both, so a line missing either is invisible to the loss report.
    The subtotal is then recalculated, which drops the line from the bill.

    Refuses to void the last live line. That is what a cashier does too -- a
    whole ticket is cancelled, not voided a line at a time -- and it matters
    here: voiding the only line leaves a COMPLETED order at subtotal 0.00 with
    paid_amount restated down to zero, which is a paid order with no revenue in
    it. That row then counts as an order in the sales summary while
    contributing nothing to it.
    """
    live = [i for i in order.items if not i.is_deleted]
    if len(live) < 2:
        return None
    line = rng.choice(live)
    line.is_deleted = True
    line.prep_status = PREP_VOIDED
    line.void_reason = rng.choice([
        "Customer changed their mind",
        "Wrong dish rung in",
        "Kitchen ran out of prepped base",
    ])
    line.voided_at = when
    line.voided_by = user_id
    return line


def _pay(order, method, user_id, when, amount=None):
    """Record a successful payment covering the bill."""
    value = amount if amount is not None else order.total_amount
    payment = CMSPayment(
        order_id=order.id,
        amount=value,
        payment_method=PaymentMethodEnum(method),
        payment_status=PaymentStatusEnum.PAID,
        paid_at=when,
        created_by=user_id,
        created_at=when,
        updated_at=when,
    )
    payment.mark_success(
        transaction_ref=f"DEMO-{order.order_number}", verified_by=user_id
    )
    # mark_success stamps paid_at with the real clock. Backdate it to match
    # the order, or a 14-day history all shows as settled in the last minute
    # and the payment timeline disagrees with the order it belongs to.
    payment.paid_at = when
    payment.verified_at = when
    db_session.add(payment)
    order.paid_amount = value
    return payment


def _create_order(sequence, *, reference_type, reference_id, table_id, customer_id,
                  status, order_type, ordered_at, notes, created_by):
    order = CMSOrder(
        order_number=sequence.generate("order"),
        reference_type=reference_type,
        reference_id=reference_id,
        table_id=table_id,
        customer_id=customer_id,
        status=status,
        order_type=order_type,
        payment_status=PaymentStatusEnum.PENDING,
        notes=notes,
        ## NOT NULL with no default. An order with no actor cannot be
        ## attributed in the reports or the order list.
        created_by=created_by,
        ordered_at=ordered_at,
        created_at=ordered_at,
        updated_at=ordered_at,
        is_deleted=False,
    )
    db_session.add(order)
    db_session.flush()
    return order


def seed_orders():
    rng = random.Random(20261011)

    if _already_seeded():
        print(f"--- Orders already seeded (notes begin {SEED_MARKER!r}); skipping. ---")
        return 0

    if not _load_recipes():
        raise LookupError(
            "order_seeder: no active recipes. Run recipe_seeder first -- an "
            "order line is meaningless without something to sell."
        )
    tables = _load_tables()
    if not tables:
        raise LookupError(
            "order_seeder: no tables. Run floor_plan_seeder first."
        )
    customers = _load_customers()
    user = _load_user()
    recipes = _load_recipes()
    sequence = DocumentSequenceService(db_session)
    ## Looked up by id rather than via order.customer: the order is built with
    ## customer_id set directly, so the relationship is not populated.
    customer_by_id = {c.id: c for c in customers}

    tz = business_timezone()
    today = datetime.now(tz).date()
    created = 0
    occupied_table_ids = set()

    ## ------------------------------------------------------------------
    ## History: completed sales, the bulk of what the reports read.
    ## ------------------------------------------------------------------
    for offset in range(HISTORY_DAYS, 0, -1):
        day = today - timedelta(days=offset)
        for _ in range(rng.randint(2, 4)):
            hour = rng.choice(SERVICE_HOURS)
            minute = rng.choice([0, 7, 15, 22, 30, 38, 45, 51])
            ordered_at = _local_to_utc_naive(day, hour, minute)

            order_type = rng.choice(ORDER_TYPES)
            is_dine_in = order_type == OrderTypeEnum.DINE_IN.value

            ## Walk-in vs customer vs table. Only dine-in seats a table, and
            ## only two thirds of those are on the book.
            customer_id = None
            table_id = None
            if is_dine_in and rng.random() < 0.7:
                table = rng.choice(tables)
                table_id = table.id
                reference_type, reference_id = "table", table.id
            elif customers and rng.random() < 0.5:
                customer = rng.choice(customers)
                customer_id = customer.id
                reference_type, reference_id = "customer", customer.id
            else:
                reference_type, reference_id = "walkin", 0

            notes = f"{SEED_MARKER} seeded sale, {day.isoformat()} {hour:02d}:{minute:02d}"
            order = _create_order(
                sequence,
                reference_type=reference_type,
                reference_id=reference_id,
                table_id=table_id,
                customer_id=customer_id,
                status=OrderStatusEnum.COMPLETED,
                order_type=order_type,
                ordered_at=ordered_at,
                notes=notes,
                created_by=user.id,
            )
            created += 1

            ## Decided before the lines are drawn. _void_one_line refuses to void an
            ## order's last live line, so an order earmarked for a void has to
            ## be built with room to lose one -- otherwise the refusal silently
            ## eats the void and the loss report thins out to nothing.
            will_void = rng.random() < 0.12

            lo, hi = PREP_MINUTES_RANGE
            prep_minutes = rng.randint(lo, hi)
            prep_window = (
                ordered_at + timedelta(minutes=2),
                ordered_at + timedelta(minutes=2 + prep_minutes),
            )
            _build_items(order, recipes, rng, PREP_READY, prep_window,
                         min_lines=2 if will_void else 1)

            ## Totals come off the live lines, so a discount applied here is
            ## reflected in total_amount rather than drifting from the header.
            order.calculate_totals()
            if rng.random() < 0.15:
                order.discount_amount = (
                    order.subtotal * Decimal("0.10")
                ).quantize(Decimal("0.01"))
                order.calculate_totals()

            order.completed_at = prep_window[1] + timedelta(minutes=rng.randint(5, 40))
            order.status = OrderStatusEnum.COMPLETED
            order.paid_amount = Decimal("0.00")
            _pay(order, rng.choice(PAYMENT_METHODS), user.id, order.completed_at)
            order.update_payment_status()

            ## A cashier void on roughly one order in eight. Voiding before the
            ## payment is what makes it a real loss event rather than a refund.
            if will_void:
                voided_at = prep_window[0] + timedelta(minutes=rng.randint(1, 10))
                if _void_one_line(order, rng, user.id, voided_at) is not None:
                    order.calculate_totals()
                    order.update_payment_status()
                    ## Restate the payment against the reduced bill. Left as the
                    ## pre-void figure the order would read as overpaid, which
                    ## paid >= total would still accept -- so nothing downstream
                    ## would flag it, and the refund would simply not exist.
                    order.paid_amount = order.total_amount
                    order.update_payment_status()
                    ## The payment row too: the payment breakdown report sums
                    ## cms_payments.amount, so a stale pre-void figure there
                    ## makes takings disagree with order totals.
                    for payment in order.payments:
                        payment.amount = order.total_amount

            ## Banked last, on the post-void bill. This is what
            ## CMSOrder.complete() does as a side effect; assigning the status
            ## directly skips it, and the effect is not cosmetic. The customer
            ## report's lifetime leaderboard filters on total_visits > 0, and
            ## the customer screen shows the counters, so an order referencing a
            ## customer without incrementing them leaves a regular reading
            ## "0 visits" beside a full order history.
            customer = customer_by_id.get(order.customer_id) if order.customer_id else None
            if customer is not None:
                customer.record_visit(order.total_amount)

    ## ------------------------------------------------------------------
    ## Cancelled orders: the second loss channel in the void report, kept
    ## deliberately separate from cashier voids in the data as in the report.
    ## ------------------------------------------------------------------
    for offset in range(HISTORY_DAYS - 2, 0, -1):
        day = today - timedelta(days=offset)
        if rng.random() > 0.4:
            continue
        hour = rng.choice([13, 14, 20, 21])
        ordered_at = _local_to_utc_naive(day, hour, rng.choice([5, 18, 40]))
        table = rng.choice(tables)

        order = _create_order(
            sequence,
            reference_type="table",
            reference_id=table.id,
            table_id=table.id,
            customer_id=None,
            status=OrderStatusEnum.PENDING,
            order_type=OrderTypeEnum.DINE_IN.value,
            ordered_at=ordered_at,
            notes=f"{SEED_MARKER} seeded cancellation, {day.isoformat()}",
            created_by=user.id,
        )
        created += 1
        _build_items(order, recipes, rng, PREP_PENDING, (None, None))
        order.calculate_totals()

        cancelled_at = ordered_at + timedelta(minutes=rng.randint(4, 25))
        reason = rng.choice([
            "Customer walked out",
            "Kitchen could not start the dish",
            "Duplicate ticket",
        ])
        order.status = OrderStatusEnum.CANCELLED
        order.cancelled_at = cancelled_at
        order.cancelled_reason = reason
        order.updated_by = user.id

        ## Cancel stamps every line as voided but deliberately does NOT set
        ## is_deleted, matching OrderService.cancel_order. That is what keeps
        ## cancelled lines out of the cashier-void grouping while the report
        ## still counts the order itself under cancelled_value.
        for line in order.items:
            line.prep_status = PREP_VOIDED
            line.void_reason = f"Order cancelled: {reason}"
            line.voided_at = cancelled_at
            line.voided_by = user.id
        # total_amount is left as it stood: the void report wants cancelled
        # orders valued at the amount that almost left the till.

    ## ------------------------------------------------------------------
    ## Live tickets for the KDS and the open-table tiles, dated today.
    ## ------------------------------------------------------------------
    live_plan = [
        (OrderStatusEnum.PENDING, PREP_PENDING),
        (OrderStatusEnum.CONFIRMED, PREP_PENDING),
        (OrderStatusEnum.PREPARING, PREP_PREPARING),
        (OrderStatusEnum.PREPARING, PREP_PREPARING),
    ]
    used_tables = set()
    for status, prep_state in live_plan:
        hour = min(21, max(8, datetime.now(tz).hour - rng.randint(0, 2)))
        ordered_at = _local_to_utc_naive(
            today, hour, rng.choice([0, 10, 20, 35, 50])
        )
        ## A table can only hold one open ticket, otherwise the floor shows
        ## two parties on one table and the active-order lookup is ambiguous.
        free = [t for t in tables if t.id not in used_tables]
        if not free:
            break
        table = rng.choice(free)
        used_tables.add(table.id)

        order = _create_order(
            sequence,
            reference_type="table",
            reference_id=table.id,
            table_id=table.id,
            customer_id=rng.choice(customers).id if customers else None,
            status=status,
            order_type=OrderTypeEnum.DINE_IN.value,
            ordered_at=ordered_at,
            notes=f"{SEED_MARKER} live ticket ({status.value})",
            created_by=user.id,
        )
        created += 1

        _build_items(
            order, recipes, rng, prep_state,
            (None, None) if prep_state != PREP_READY
            else (ordered_at, ordered_at + timedelta(minutes=15)),
        )
        order.calculate_totals()

        ## Status is assigned at construction rather than through confirm() /
        ## start_preparing(): those assert the preceding state, and an order
        ## created already-CONFIRMED cannot legally walk the transition.
        ## Only the timestamp companion has to be set by hand.
        if status == OrderStatusEnum.CONFIRMED:
            order.confirmed_at = ordered_at + timedelta(minutes=1)
        occupied_table_ids.add(table.id)

    ## Live tickets hold their tables; everything else must be free or the
    ## floor screen cannot seat a walk-in.
    for table in tables:
        table.status = "occupied" if table.id in occupied_table_ids else "available"
        table.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    return created


def seed_cms_orders():
    try:
        created = seed_orders()
        db_session.commit()
        print(f"--- Orders seeded. ({created} created) ---")

    except Exception as exc:
        db_session.rollback()
        print(f"!!! Order seeder FAILED: {_safe(str(exc))[:300]}")
        raise

    finally:
        db_session.remove()


if __name__ == "__main__":
    seed_cms_orders()