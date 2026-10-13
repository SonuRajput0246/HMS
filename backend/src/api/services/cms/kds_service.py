from src.api.utils.datetime_helper import utcnow
from src.api.models.cms.order_model import (
    CMSOrder,
    CMSOrderItem,
    OrderStatusEnum,
    PREP_PENDING,
    PREP_PREPARING,
    PREP_READY,
    PREP_VOIDED,
)
from src.api.utils.responses import service_response


## Orders in these states are still live in the kitchen. A completed or
## cancelled order must never appear on a KDS board, even if a line was somehow
## left mid-prep.
LIVE_ORDER_STATUSES = [
    OrderStatusEnum.PENDING.value,
    OrderStatusEnum.CONFIRMED.value,
    OrderStatusEnum.PREPARING.value,
    OrderStatusEnum.READY.value,
    OrderStatusEnum.SERVED.value,
]

## Lines that still need kitchen attention.
QUEUE_PREP_STATUSES = [PREP_PENDING, PREP_PREPARING]


class KdsService:
    """Kitchen Display System.

    Read-heavy and latency-sensitive: every call here is something a chef's
    screen re-polls, so the queries are deliberately narrow -- one join for the
    ticket list rather than a lazy load per order.
    """

    def __init__(self, db):
        self.db = db

    ## ==================================================================
    ## READS
    ## ==================================================================

    def get_tickets(self, data: dict):
        """The kitchen queue, one entry per order that still owes kitchen work.

        A ticket appears if ANY of its lines is pending or preparing. Lines that
        are ready or voided are still included (so the chef can see the whole
        order) unless include_ready is false and every line is done.
        """
        station = data.get("station")
        include_ready = data.get("include_ready", False)
        order_by = data.get("order_by", "oldest_first")

        query = self.db.query(CMSOrder).filter(
            CMSOrder.is_deleted == False,
            CMSOrder.status.in_(LIVE_ORDER_STATUSES)
        )

        ## Restrict to orders that have at least one line at this station in the
        ## queue. Done as a subquery rather than by fetching and filtering in
        ## Python, so the board stays fast as the order history grows.
        item_filter = [
            CMSOrderItem.is_deleted == False,
            CMSOrderItem.order_id == CMSOrder.id,
            CMSOrderItem.prep_status.in_(QUEUE_PREP_STATUSES),
        ]
        if station:
            item_filter.append(CMSOrderItem.station == station)

        query = query.filter(self.db.query(CMSOrderItem.id).filter(*item_filter).exists())

        if order_by == "newest_first":
            query = query.order_by(CMSOrder.ordered_at.desc(), CMSOrder.id.desc())
        else:
            query = query.order_by(CMSOrder.ordered_at.asc(), CMSOrder.id.asc())

        orders = query.all()

        tickets = [self._serialize_ticket(o, station, include_ready) for o in orders]
        tickets = [t for t in tickets if t is not None]

        ## Overdue first when the chef asked for the default ordering: a dish
        ## waiting 25 minutes matters more than one waiting 2. Kept out of the
        ## SQL ORDER BY because the queue is small and the elapsed time is
        ## computed in Python anyway.
        if order_by == "oldest_first":
            tickets.sort(key=lambda t: t["max_wait_minutes"], reverse=True)

        summary = {
            "pending": 0,
            "preparing": 0,
            "ready": 0,
        }
        for ticket in tickets:
            for line in ticket["items"]:
                if line["prep_status"] in summary:
                    summary[line["prep_status"]] += 1

        return service_response(
            True,
            "KDS tickets fetched successfully.",
            {
                "station": station,
                "tickets": tickets,
                "ticket_count": len(tickets),
                "summary": summary,
                "server_time": utcnow().isoformat()
            },
            200
        )

    def get_ticket(self, order_id: int):
        """One ticket in full, for the KDS drill-down view."""
        order = self.db.query(CMSOrder).filter_by(is_deleted=False, id=order_id).first()
        if not order:
            return service_response(False, "Order not found", None, 404)

        ticket = self._serialize_ticket(order, station=None, include_ready=True)
        if ticket is None:
            return service_response(
                False, "This order has no items waiting in the kitchen.", None, 409
            )

        return service_response(True, "Ticket fetched successfully.", ticket, 200)

    def get_station_summary(self):
        """Per-station outstanding counts, for the KDS station switcher.

        Drives the badge on each station tab so a cook can see at a glance which
        pass is backing up without visiting every screen.
        """
        rows = (
            self.db.query(
                CMSOrderItem.station,
                CMSOrderItem.prep_status,
            )
            .join(CMSOrder, CMSOrder.id == CMSOrderItem.order_id)
            .filter(
                CMSOrderItem.is_deleted == False,
                CMSOrderItem.prep_status.in_(QUEUE_PREP_STATUSES),
                CMSOrder.status.in_(LIVE_ORDER_STATUSES)
            )
            .all()
        )

        by_station = {}
        for station, prep_status in rows:
            key = station or "unassigned"
            entry = by_station.setdefault(
                key, {"station": station, "pending": 0, "preparing": 0, "total": 0}
            )
            if prep_status in entry:
                entry[prep_status] += 1
            entry["total"] += 1

        ## One entry per station even when it is idle, so the tab list does not
        ## shift around as orders come and go.
        for station in self._known_stations():
            by_station.setdefault(
                station, {"station": station, "pending": 0, "preparing": 0, "total": 0}
            )

        return service_response(
            True,
            "Station summary fetched successfully.",
            {"stations": list(by_station.values())},
            200
        )

    ## ==================================================================
    ## WRITES
    ## ==================================================================

    def update_prep_status(self, order_id: int, data: dict):
        """Advance or rewind one line through the kitchen."""
        order = self.db.query(CMSOrder).filter_by(is_deleted=False, id=order_id).first()
        if not order:
            return service_response(False, "Order not found", None, 404)

        if order.status in (OrderStatusEnum.COMPLETED, OrderStatusEnum.CANCELLED):
            return service_response(
                False,
                f"Order is '{order.status}' and its kitchen status cannot change.",
                None, 409
            )

        item = self.db.query(CMSOrderItem).filter_by(
            is_deleted=False, id=data["order_item_id"], order_id=order.id
        ).first()
        if not item:
            return service_response(
                False, "Order item not found on this order.", None, 404
            )

        target = data["prep_status"]

        try:
            if target == PREP_PENDING:
                ## Requeue. Clears both stamps so the elapsed timer restarts.
                item.prep_status = PREP_PENDING
                item.prep_started_at = None
                item.prep_completed_at = None
            elif target == PREP_PREPARING:
                item.start_prep()
            else:
                item.mark_ready()
        except ValueError as exc:
            return service_response(False, str(exc), None, 409)

        self.db.commit()
        self.db.refresh(item)

        ## Once the kitchen has started, the order header follows along so the
        ## POS stops showing a confirmed order the chef is already cooking.
        self._sync_order_status(order)

        return service_response(
            True,
            "Item prep status updated successfully.",
            self._serialize_item(item, order),
            200
        )

    def bump_order(self, data: dict):
        """Mark every still-cooking line on one ticket ready.

        Restricted to one station when given, because a table's grill items and
        bar items go out at different times and the grill chef must not clear
        the cocktail.
        """
        order_id = data["order_id"]
        station = data.get("station")

        order = self.db.query(CMSOrder).filter_by(is_deleted=False, id=order_id).first()
        if not order:
            return service_response(False, "Order not found", None, 404)

        query = self.db.query(CMSOrderItem).filter(
            CMSOrderItem.is_deleted == False,
            CMSOrderItem.order_id == order.id,
            CMSOrderItem.prep_status.in_(QUEUE_PREP_STATUSES),
        )
        if station:
            query = query.filter(CMSOrderItem.station == station)

        items = query.all()
        if not items:
            return service_response(
                False,
                "No items on this order are waiting in the kitchen.",
                None, 409
            )

        for item in items:
            item.mark_ready()

        self.db.commit()

        order = self.db.query(CMSOrder).filter_by(id=order.id).first()
        self._sync_order_status(order)

        return service_response(
            True,
            f"{len(items)} item(s) marked ready.",
            {
                "order_id": order.id,
                "bumped_count": len(items),
                "order_status": order.status.value
            },
            200
        )

    ## ==================================================================
    ## internals
    ## ==================================================================

    def _sync_order_status(self, order: CMSOrder) -> None:
        """Advance the order header to match what the kitchen has actually done.

        - any line preparing -> order is preparing
        - every line ready/voided -> order is ready

        Only ever moves forward except the ready step, and never past served.
        The write is committed separately because callers have usually already
        committed the line change.
        """
        if order is None:
            return

        live_items = [i for i in order.items if not i.is_deleted]
        if not live_items:
            return

        pending = [i for i in live_items if i.is_in_kitchen_queue()]
        preparing = [i for i in live_items if i.prep_status == PREP_PREPARING]

        target = None
        if preparing:
            target = OrderStatusEnum.PREPARING
        elif not pending:
            target = OrderStatusEnum.READY

        if target is None:
            return

        current = order.status
        forward = {
            OrderStatusEnum.PENDING: [OrderStatusEnum.PREPARING],
            OrderStatusEnum.CONFIRMED: [OrderStatusEnum.PREPARING],
            OrderStatusEnum.PREPARING: [OrderStatusEnum.READY],
        }

        if target in forward.get(current, []):
            order.status = target
            self.db.commit()

    def _known_stations(self):
        """Station list straight from the enum tables, matching the recipe form."""
        try:
            from src.api.utils.enum_helper import EnumHelper
            return list(EnumHelper(self.db).active_values("recipe_station"))
        except Exception:
            ## Enum tables unreadable should not take down the KDS. The badge
            ## list degrades to whatever the live query found.
            return []

    def _serialize_ticket(self, order: CMSOrder, station=None, include_ready: bool = False):
        """One order as a KDS ticket, or None when it has nothing to show."""
        ordered_at = order.ordered_at

        items = []
        max_wait = 0

        for item in order.items:
            if item.is_deleted:
                continue
            if station and item.station != station:
                continue

            ## Default view hides plated lines; drill-down passes
            ## include_ready=True to show the whole order.
            if not include_ready and item.prep_status not in QUEUE_PREP_STATUSES:
                continue

            payload = self._serialize_item(item, order)
            wait = payload["minutes_since_ordered"] or 0
            max_wait = max(max_wait, wait)
            items.append(payload)

        if not items:
            return None

        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "reference_label": order.get_reference_label(),
            "table_id": order.table_id,
            "table_number": order.table.table_number if order.table else None,
            "order_type": order.order_type.value,
            "order_status": order.status.value,
            "ordered_at": ordered_at.isoformat() if ordered_at else None,
            "max_wait_minutes": max_wait,
            "kitchen_notes": order.kitchen_notes,
            "item_count": len(items),
            "items": items
        }

    def _serialize_item(self, item: CMSOrderItem, order: CMSOrder) -> dict:
        return {
            "id": item.id,
            "order_id": item.order_id,
            "item_name": item.item_name,
            "quantity": str(item.quantity),
            "station": item.station,
            "prep_status": item.prep_status,
            "modifiers": item.modifiers,
            "cooking_instructions": item.cooking_instructions,
            "spice_level": item.spice_level,
            "prep_started_at": item.prep_started_at.isoformat() if item.prep_started_at else None,
            "prep_completed_at": item.prep_completed_at.isoformat() if item.prep_completed_at else None,
            "minutes_in_prep": item.minutes_in_prep(),
            "minutes_since_ordered": item.minutes_since_ordered(
                order.ordered_at if order else None
            )
        }