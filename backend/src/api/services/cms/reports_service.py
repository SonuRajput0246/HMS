from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, text

from src.api.models.cms.order_model import (
    CMSOrder,
    CMSOrderItem,
    CMSPayment,
    OrderStatusEnum,
    OrderTypeEnum,
    PaymentStatusEnum,
    PREP_VOIDED,
)
from src.api.models.cms.customer_model import Customer
from src.api.models.cms.table_model import Table
from src.api.models.common.user_model import User
from src.api.utils.datetime_helper import (
    business_timezone,
    business_timezone_name,
    iter_local_days,
    resolve_report_range,
)
from src.api.utils.responses import service_response


## Only settled orders count towards revenue. An open order has a total_amount
## that is a quote, not a sale, and counting it makes every report move while
## the guest is still eating.
SOLD_STATUS = OrderStatusEnum.COMPLETED.value

ZERO = Decimal("0.00")


class ReportRangeError(ValueError):
    """An unusable report window: unknown preset, or an inverted custom range."""


def _d(value) -> Decimal:
    """Decimal from a DB aggregate, tolerating None and float."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class ReportsService:
    """Sales, item and loss reporting.

    Two rules shape everything here.

    1. Revenue counts settled orders only, and reads CMSOrder.total_amount
       rather than re-summing lines -- at this point the header is the amount
       the customer actually agreed to pay.

    2. Every date boundary is a trading-timezone boundary converted to UTC, and
       ranges are half-open [start, end). Reports are grouped by UTC hour in
       SQL (cheap, index-friendly) and the shift into local time happens in
       Python over a few dozen rows, instead of asking MySQL to CONVERT_TZ
       per row.
    """

    def __init__(self, db):
        self.db = db

    ## ==================================================================
    # SALES SUMMARY
    # ==================================================================

    def get_sales_summary(self, data: dict):
        """Headline figures for the period, plus the breakdowns the owner asks
        for first: how they paid, and how they ordered."""
        start, end, from_day, to_day = self._resolve(data)

        base = self._sold_orders_query(start, end)

        totals = base.with_entities(
            func.count(CMSOrder.id),
            func.coalesce(func.sum(CMSOrder.total_amount), 0),
            func.coalesce(func.sum(CMSOrder.discount_amount), 0),
            func.coalesce(func.sum(CMSOrder.tax_amount), 0),
            func.coalesce(func.sum(CMSOrder.paid_amount), 0),
        ).one()

        order_count = int(totals[0] or 0)
        revenue = _d(totals[1])
        discount = _d(totals[2])
        tax = _d(totals[3])
        paid = _d(totals[4])

        payload = {
            "range": self._range_meta(data, from_day, to_day),
            "totals": {
                "order_count": order_count,
                "revenue": str(revenue),
                "tax_amount": str(tax),
                "discount_amount": str(discount),
                "collected": str(paid),
                ## Outstanding on settled orders: should be 0.00, and anything
                ## else means a payment or close went wrong -- surfaced rather
                ## than buried so it gets looked at.
                "outstanding": str(max(revenue - paid, ZERO)),
                "average_ticket": str(
                    (revenue / order_count).quantize(Decimal("0.01")) if order_count else "0.00"
                ),
            },
        }

        if data.get("include_payment_breakdown", True):
            payload["by_payment_method"] = self._payment_breakdown(start, end)

        payload["by_order_type"] = self._order_type_breakdown(start, end)

        if data.get("include_hourly", True):
            payload["hourly"] = self._hourly_buckets(start, end, from_day, to_day)

        return service_response(True, "Sales summary fetched successfully.", payload, 200)

    ## ==================================================================
    # ITEM SALES
    # ==================================================================

    def get_item_sales(self, data: dict):
        """What the cafe actually sold, by recipe or by direct inventory item."""
        start, end, from_day, to_day = self._resolve(data)
        sort_by = data.get("sort_by", "quantity")
        limit = data.get("limit", 20)
        include_dead = data.get("include_dead_stock", False)
        station = data.get("station")

        sold_order_ids = self._sold_order_ids_subquery(start, end)

        filters = [
            CMSOrderItem.is_deleted == False,
            CMSOrderItem.order_id.in_(sold_order_ids),
        ]
        if station:
            filters.append(CMSOrderItem.station == station)

        ## item_name is denormalised onto the line, so this report stays
        ## correct even after a recipe is renamed or deactivated.
        rows = (
            self.db.query(
                CMSOrderItem.item_type,
                CMSOrderItem.item_id,
                CMSOrderItem.item_name,
                CMSOrderItem.station,
                func.coalesce(func.sum(CMSOrderItem.quantity), 0).label("qty"),
                func.coalesce(func.sum(CMSOrderItem.total_price), 0).label("value"),
                func.count(func.distinct(CMSOrderItem.order_id)).label("order_count"),
            )
            .filter(*filters)
            .group_by(
                CMSOrderItem.item_type,
                CMSOrderItem.item_id,
                CMSOrderItem.item_name,
                CMSOrderItem.station,
            )
            .all()
        )

        items = []
        total_qty = Decimal("0")
        total_value = ZERO

        for row in rows:
            qty = _d(row.qty)
            value = _d(row.value)
            total_qty += qty
            total_value += value
            items.append({
                "item_type": row.item_type,
                "item_id": row.item_id,
                "item_name": row.item_name,
                "station": row.station,
                "quantity_sold": str(qty),
                "revenue": str(value),
                "order_count": int(row.order_count or 0),
                ## Average per order, i.e. how many of this dish a typical
                ## table gets -- the number that matters when reordering stock.
                "quantity_per_order": str(
                    (qty / row.order_count).quantize(Decimal("0.01"))
                    if row.order_count else "0.00"
                ),
            })

        if include_dead:
            items.extend(self._dead_stock(start, end, {i["item_id"] for i in items}))

        if sort_by == "revenue":
            items.sort(key=lambda i: _d(i["revenue"]), reverse=True)
        else:
            items.sort(key=lambda i: _d(i["quantity_sold"]), reverse=True)

        truncated = items[:limit]

        return service_response(
            True,
            "Item sales fetched successfully.",
            {
                "range": self._range_meta(data, from_day, to_day),
                "sort_by": sort_by,
                "items": truncated,
                "distinct_items_sold": len(items),
                "total_quantity": str(total_qty),
                "total_revenue": str(total_value),
                "returned": len(truncated),
                "truncated": len(items) > len(truncated)
            },
            200
        )

    ## ==================================================================
    # DAILY TREND
    # ==================================================================

    def get_daily_trend(self, data: dict):
        """Revenue per trading day, for a chart."""
        start, end, from_day, to_day = self._resolve(data)
        include_zero = data.get("include_zero_days", True)

        ## Group by UTC hour rather than UTC date: a trading day in IST starts
        ## Bucketing happens in SQL against LOCAL wall-clock time -- see
        ## _local_bucket_expression for why the offset has to be applied before
        ## truncation. The result is already local, so Python only has to read
        ## the date off the bucket.
        rows = self._sold_orders_query(start, end).with_entities(
            self._local_bucket_expression(CMSOrder.completed_at),
            func.count(CMSOrder.id),
            func.coalesce(func.sum(CMSOrder.total_amount), 0),
        ).group_by("bucket").all()

        per_day = {}
        for row in rows:
            try:
                local = datetime.strptime(row.bucket, "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                ## Defensive: a NULL completed_at yields None. Skip rather than
                ## abort the whole report over one malformed row.
                continue

            entry = per_day.setdefault(local.date(), {"orders": 0, "revenue": ZERO})
            entry["orders"] += int(row[1] or 0)
            entry["revenue"] += _d(row[2])

        series = []
        for day in iter_local_days(from_day, to_day):
            entry = per_day.get(day)
            orders_n = entry["orders"] if entry else 0
            revenue = entry["revenue"] if entry else ZERO
            if not include_zero and orders_n == 0:
                continue
            series.append({
                "date": day.isoformat(),
                "order_count": orders_n,
                "revenue": str(revenue),
                "average_ticket": str(
                    (revenue / orders_n).quantize(Decimal("0.01")) if orders_n else "0.00"
                ),
            })

        active = [s for s in series if s["order_count"] > 0]
        total_revenue = sum((_d(s["revenue"]) for s in series), ZERO)

        return service_response(
            True,
            "Daily trend fetched successfully.",
            {
                "range": self._range_meta(data, from_day, to_day),
                "series": series,
                "day_count": len(series),
                "trading_days": len(active),
                "total_revenue": str(total_revenue),
                "best_day": max(active, key=lambda s: _d(s["revenue"]), default=None),
                "average_daily_revenue": str(
                    (total_revenue / len(active)).quantize(Decimal("0.01"))
                    if active else "0.00"
                )
            },
            200
        )

    ## ==================================================================
    # VOID / LOSS
    # ==================================================================

    def get_void_report(self, data: dict):
        """Voided lines and cancelled orders: money that nearly left the till.

        Grouped by staff because the useful question is not "how much was
        voided" but "who is voiding, and is it the whole order every time".
        """
        start, end, from_day, to_day = self._resolve(data)
        group_by_staff = data.get("group_by_staff", True)
        limit = data.get("limit", 100)

        rows = (
            self.db.query(
                CMSOrderItem.voided_by,
                CMSOrderItem.void_reason,
                CMSOrderItem.item_name,
                func.coalesce(func.sum(CMSOrderItem.total_price), 0).label("value"),
                func.coalesce(func.sum(CMSOrderItem.quantity), 0).label("qty"),
                func.count(func.distinct(CMSOrderItem.order_id)).label("orders"),
                func.count(CMSOrderItem.id).label("lines"),
            )
            .join(CMSOrder, CMSOrder.id == CMSOrderItem.order_id)
            .filter(
                CMSOrderItem.is_deleted == True,
                CMSOrderItem.prep_status == PREP_VOIDED,
                CMSOrderItem.voided_at >= start,
                CMSOrderItem.voided_at < end,
                CMSOrder.is_deleted == False,
            )
            .group_by(
                CMSOrderItem.voided_by,
                CMSOrderItem.void_reason,
                CMSOrderItem.item_name,
            )
            .order_by(func.sum(CMSOrderItem.total_price).desc())
            .all()
        )

        entries = []
        by_staff = {}
        total_value = ZERO

        for row in rows:
            value = _d(row.value)
            total_value += value

            staff = None
            if row.voided_by:
                staff = self.db.query(User).filter_by(id=row.voided_by).first()
                staff_name = (
                    f"{(staff.first_name or '').strip()} {(staff.last_name or '').strip()}".strip()
                    or staff.email
                    if staff else f"user #{row.voided_by}"
                )
            else:
                staff_name = "System / unknown"

            entry = {
                "voided_by": row.voided_by,
                "voided_by_name": staff_name,
                "void_reason": row.void_reason,
                "item_name": row.item_name,
                "line_count": int(row.lines or 0),
                "order_count": int(row.orders or 0),
                "quantity": str(_d(row.qty)),
                "value": str(value),
            }
            entries.append(entry)

            if group_by_staff:
                bucket = by_staff.setdefault(
                    staff_name,
                    {"voided_by": row.voided_by, "voided_by_name": staff_name,
                     "line_count": 0, "order_count": 0, "total_value": ZERO},
                )
                bucket["line_count"] += int(row.lines or 0)
                bucket["order_count"] += int(row.orders or 0)
                bucket["total_value"] += value

        ## Cancelled orders are a separate loss channel from a cashier void, so
        ## they are reported on their own rather than folded into the same total.
        cancelled = (
            self.db.query(CMSOrder)
            .filter(
                CMSOrder.is_deleted == False,
                CMSOrder.status == OrderStatusEnum.CANCELLED.value,
                CMSOrder.cancelled_at >= start,
                CMSOrder.cancelled_at < end,
            )
            .all()
        )
        cancelled_value = sum(
            ((o.total_amount or ZERO) for o in cancelled), ZERO
        )

        payload = {
            "range": self._range_meta(data, from_day, to_day),
            "entries": entries[:limit],
            "total_void_value": str(total_value),
            "total_void_lines": sum(e["line_count"] for e in entries),
            "cancelled_orders": len(cancelled),
            "cancelled_value": str(cancelled_value),
            "combined_loss": str(total_value + cancelled_value),
        }

        if group_by_staff:
            payload["by_staff"] = sorted(
                [{**v, "total_value": str(v["total_value"])} for v in by_staff.values()],
                key=lambda s: _d(s["total_value"]),
                reverse=True,
            )

        return service_response(True, "Void report fetched successfully.", payload, 200)

    ## ==================================================================
    # internals
    # ==================================================================

    def _resolve(self, data: dict):
        """Preset/date pair -> (start_utc, end_utc, from_day, to_day)."""
        try:
            return resolve_report_range(
                data.get("range", "today"),
                data.get("from_date"),
                data.get("to_date"),
            )
        except ValueError as exc:
            ## A bad preset or an inverted custom range is caller error, not a
            ## server fault, so it is a 400 with the reason attached.
            raise ReportRangeError(str(exc)) from exc

    def _range_meta(self, data: dict, from_day: date, to_day: date) -> dict:
        start, end, _, _ = resolve_report_range(
            data.get("range", "today"), data.get("from_date"), data.get("to_date")
        )
        return {
            "preset": data.get("range", "today"),
            "from_date": from_day.isoformat(),
            "to_date": to_day.isoformat(),
            "day_count": (to_day - from_day).days + 1,
            "timezone": business_timezone_name(),
            ## Echoed so the client can verify it is asking about the right
            ## window without re-deriving the calendar maths.
            "utc_start": start.isoformat(),
            "utc_end_exclusive": end.isoformat(),
        }

    def _sold_orders_query(self, start, end):
        """Settled orders completed inside [start, end)."""
        return self.db.query(CMSOrder).filter(
            CMSOrder.is_deleted == False,
            CMSOrder.status == SOLD_STATUS,
            CMSOrder.completed_at >= start,
            CMSOrder.completed_at < end,
        )

    def _sold_order_ids_subquery(self, start, end):
        return (
            self.db.query(CMSOrder.id)
            .filter(
                CMSOrder.is_deleted == False,
                CMSOrder.status == SOLD_STATUS,
                CMSOrder.completed_at >= start,
                CMSOrder.completed_at < end,
            )
        )

    def _payment_breakdown(self, start, end) -> list:
        """Collected cash by method.

        Reads CMSPayment rather than the order, because one order can be settled
        by several payments and the method breakdown is about what the customer
        actually handed over.
        """
        rows = (
            self.db.query(
                CMSPayment.payment_method,
                func.count(CMSPayment.id),
                func.coalesce(func.sum(CMSPayment.amount), 0),
            )
            .join(CMSOrder, CMSOrder.id == CMSPayment.order_id)
            .filter(
                CMSPayment.is_deleted == False,
                CMSPayment.payment_status == PaymentStatusEnum.PAID,
                CMSOrder.is_deleted == False,
                CMSOrder.completed_at >= start,
                CMSOrder.completed_at < end,
            )
            .group_by(CMSPayment.payment_method)
            .all()
        )

        total = sum((_d(r[2]) for r in rows), ZERO)
        breakdown = []
        for method, count, amount in rows:
            value = _d(amount)
            breakdown.append({
                "payment_method": method.value if hasattr(method, "value") else str(method),
                "payment_count": int(count or 0),
                "amount": str(value),
                "share_percent": str(
                    ((value / total) * Decimal("100")).quantize(Decimal("0.01")) if total else "0.00"
                ),
            })

        breakdown.sort(key=lambda b: _d(b["amount"]), reverse=True)
        return breakdown

    def _order_type_breakdown(self, start, end) -> list:
        rows = (
            self._sold_orders_query(start, end)
            .with_entities(
                CMSOrder.order_type,
                func.count(CMSOrder.id),
                func.coalesce(func.sum(CMSOrder.total_amount), 0),
            )
            .group_by(CMSOrder.order_type)
            .all()
        )
        return [
            {
                "order_type": otype.value if hasattr(otype, "value") else str(otype),
                "order_count": int(count or 0),
                "revenue": str(_d(value)),
            }
            for otype, count, value in rows
        ]

    def _hourly_buckets(self, start, end, from_day, to_day) -> dict:
        """Revenue by trading day, then by hour of that day.

        "Which hours are we busy" is the staffing question, so hours are
        expressed in trading-local time: an 11:00 slot means 11:00 at the till.
        Bucketing is done in SQL against local wall-clock time (see
        _local_bucket_expression) so a half-hour zone still lands correctly.
        """
        rows = self._sold_orders_query(start, end).with_entities(
            self._local_bucket_expression(CMSOrder.completed_at),
            func.count(CMSOrder.id),
            func.coalesce(func.sum(CMSOrder.total_amount), 0),
        ).group_by("bucket").all()

        by_day = {}
        for row in rows:
            try:
                local = datetime.strptime(row.bucket, "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue
            day = by_day.setdefault(local.date(), {})
            hour = day.get(local.hour, {"order_count": 0, "revenue": ZERO})
            hour["order_count"] += int(row[1] or 0)
            hour["revenue"] += _d(row[2])
            day[local.hour] = hour

        result = {}
        for day in iter_local_days(from_day, to_day):
            hours = []
            for hour in range(24):
                entry = by_day.get(day, {}).get(hour)
                hours.append({
                    "hour": hour,
                    "label": f"{hour:02d}:00",
                    "order_count": entry["order_count"] if entry else 0,
                    "revenue": str(entry["revenue"] if entry else ZERO),
                })
            result[day.isoformat()] = hours

        return result

    def _local_bucket_expression(self, column):
        """SQL expression yielding LOCAL wall-clock 'YYYY-MM-DD HH:00:00'.

        The offset is applied in SQL, BEFORE date_format truncates, which is the
        only order that works in a half-hour zone. Truncating in UTC first and
        shifting afterwards is wrong for IST: an order at 07:30 UTC is 13:00
        local, but the UTC hour bucket 07:00 shifts to 12:30, so the order lands
        in local hour 12 instead of 13. More precisely, a UTC hour [07:00, 08:00)
        spans local 12:30-13:30 and straddles two local hours, so a UTC hour
        bucket can never be shifted cleanly into one local hour.

        The offset is fixed for the zone at report time. Exact for IST
        (UTC+05:30, no DST) and every DST-free zone; in a DST zone the offset
        shifts mid-range and buckets inside the transition hour can be an hour
        out, which is acceptable for a staffing chart.
        """
        tz = business_timezone()
        offset_minutes = int(datetime.now(tz).utcoffset().total_seconds() // 60)
        shifted = func.date_add(column, text(f"INTERVAL {offset_minutes} MINUTE"))
        return func.date_format(shifted, "%Y-%m-%d %H:00:00").label("bucket")

        result = {}
        for day in iter_local_days(from_day, to_day):
            hours = []
            for hour in range(24):
                entry = by_day.get(day, {}).get(hour)
                hours.append({
                    "hour": hour,
                    "label": f"{hour:02d}:00",
                    "order_count": entry["order_count"] if entry else 0,
                    "revenue": str(entry["revenue"] if entry else ZERO),
                })
            result[day.isoformat()] = hours

        return result

    def _dead_stock(self, start, end, sold_item_ids) -> list:
        """Active sellable items that sold nothing in the window.

        Bounded to what the cafe can actually sell now: inactive recipes, 86'd
        dishes and deleted ones are not "dead stock", they are retired.
        """
        from src.api.models.cms.recipe_model import Recipe

        sold = sold_item_ids or set()
        recipes = (
            self.db.query(Recipe)
            .filter(
                Recipe.is_deleted == False,
                Recipe.is_active == True,
                Recipe.is_available == True,
            )
            .all()
        )
        return [
            {
                "item_type": "recipe",
                "item_id": r.id,
                "item_name": r.name,
                "station": r.station,
                "quantity_sold": "0.00",
                "revenue": "0.00",
                "order_count": 0,
                "quantity_per_order": "0.00",
                "is_dead_stock": True,
            }
            for r in recipes
            if r.id not in sold
        ]