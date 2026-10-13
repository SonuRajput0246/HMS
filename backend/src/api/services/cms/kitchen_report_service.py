from decimal import Decimal
import logging

from sqlalchemy import func
from sqlalchemy.sql.expression import literal_column

## MySQL's TIMESTAMPDIFF takes the unit as a bare keyword, not a bound
## parameter. literal_column emits it unquoted so the statement compiles to
## timestampdiff(SECOND, a, b) rather than timestampdiff('SECOND', a, b),
## which MySQL rejects.
##
## ITS SIGNATURE IS TIMESTAMPDIFF(unit, dt1, dt2) = dt2 - dt1. The order is
## easy to get backwards and the failure is silent in the sense that it yields a
## plausible-looking NEGATIVE average rather than an error, so it is spelled out
## here and used consistently below.
SECONDS = literal_column("SECOND")

from src.api.models.cms.order_model import (
    CMSOrder,
    CMSOrderItem,
    PREP_READY,
    PREP_VOIDED,
)
from src.api.services.cms.reports_service import ReportRangeError, _d, SOLD_STATUS
from src.api.utils.datetime_helper import elapsed_minutes
from src.api.utils.responses import service_response


ZERO = Decimal("0.00")
logger = logging.getLogger(__name__)


class KitchenReportService:
    """How long the kitchen actually takes.

    The gap between "ordered" and "ready" is the number a cafe owner needs to
    decide whether they need a second grill. It is derived from two stored
    timestamps rather than a running timer, so it survives a restart and can be
    recomputed for any historical period.

    TIMING CAVEAT, and it matters: the gap includes queue time, not just cook
    time. A dish sitting behind four other tickets looks slow. That is arguably
    the more useful number -- it is what the guest experiences -- but it is not
    "cooking time", and the two should not be conflated in a report label.
    """

    def __init__(self, db):
        self.db = db

    def get_prep_performance(self, data: dict):
        try:
            from src.api.services.cms.reports_service import ReportsService
            start, end, from_day, to_day = ReportsService(self.db)._resolve(data)
        except ReportRangeError as exc:
            return service_response(False, str(exc), None, 400)

        include_by_item = data.get("include_by_item", True)
        include_pending = data.get("include_pending", False)

        filters = [
            CMSOrderItem.is_deleted == False,
            CMSOrder.is_deleted == False,
            CMSOrder.status == SOLD_STATUS,
            CMSOrder.completed_at >= start,
            CMSOrder.completed_at < end,
        ]

        ## Only finished lines contribute to a timing average. A line still
        ## pending has no prep_completed_at, and counting it as zero would drag
        ## the mean down and make a fast kitchen look slow.
        filters.append(CMSOrderItem.prep_status == PREP_READY)

        rows = (
            self.db.query(
                CMSOrderItem.item_name,
                CMSOrderItem.station,
                func.count(CMSOrderItem.id),
                func.coalesce(func.sum(CMSOrderItem.quantity), 0),
                ## Seconds, so the average is computed in SQL with integer
                ## maths rather than by pulling every timestamp into Python.
                ##
                ## TIMESTAMPDIFF reads both columns as DATETIME and does no
                ## timezone conversion, which is correct here precisely because
                ## both values are UTC. Formatting them through date_format
                ## first (as an earlier version did) would drop seconds and,
                ## more importantly, reparse strings -- fragile and slower.
                ## dt1=ordered_at, dt2=prep_completed_at, so the result is
                ## completed - ordered. Reversing these two yields a negative
                ## average instead of an error.
                func.coalesce(
                    func.sum(func.timestampdiff(
                        SECONDS, CMSOrder.ordered_at, CMSOrderItem.prep_completed_at
                    )),
                    0,
                ).label("total_seconds"),
            )
            .join(CMSOrder, CMSOrder.id == CMSOrderItem.order_id)
            .filter(*filters)
            .group_by(CMSOrderItem.item_name, CMSOrderItem.station)
            .all()
        )

        items = []
        total_lines = 0
        total_seconds = 0
        slowest = None

        for row in rows:
            lines = int(row[2] or 0)
            seconds = int(row[4] or 0)
            if lines == 0:
                continue

            avg_minutes = round(seconds / lines / 60, 1)
            entry = {
                "item_name": row.item_name,
                "station": row.station,
                "lines_completed": lines,
                "quantity": str(_d(row[3])),
                "avg_minutes": avg_minutes,
                "max_minutes": None,
            }
            items.append(entry)
            total_lines += lines
            total_seconds += seconds

            if slowest is None or avg_minutes > slowest["avg_minutes"]:
                slowest = entry

        ## A negative total means the TIMESTAMPDIFF arguments were reversed somewhere.
        ## Rather than publish a plausible-looking negative average, say so.
        if total_seconds < 0:
            logger.error(
                "KitchenReportService: negative prep duration total (%s seconds "
                "over %s lines). Check the TIMESTAMPDIFF argument order.",
                total_seconds, total_lines,
            )

        payload = {
            "range": ReportsService(self.db)._range_meta(data, from_day, to_day),
            "data_quality_warning": (
                "Negative prep durations detected; the timing figures below are "
                "unreliable."
                if total_seconds < 0 else None
            ),
            "overall": {
                "lines_completed": total_lines,
                "avg_minutes": round(total_seconds / total_lines / 60, 1) if total_lines else 0.0,
                "total_minutes": round(total_seconds / 60, 1),
            },
            "by_station": self._by_station(start, end, include_pending),
            "slowest_item": slowest,
            "note": (
                "Average includes queue time behind other tickets, not just "
                "cooking time."
            ),
        }

        if include_by_item:
            items.sort(key=lambda i: i["avg_minutes"], reverse=True)
            payload["by_item"] = items

        if include_pending:
            payload["pending_note"] = (
                "include_pending was set, but timing only counts ready lines; "
                "a pending line has no completed_at to measure against."
            )

        return service_response(True, "Kitchen performance fetched successfully.", payload, 200)

    def _by_station(self, start, end, include_pending) -> list:
        """Average wait per station, for spotting the backed-up pass."""
        filters = [
            CMSOrderItem.is_deleted == False,
            CMSOrder.is_deleted == False,
            CMSOrder.status == SOLD_STATUS,
            CMSOrder.completed_at >= start,
            CMSOrder.completed_at < end,
            CMSOrderItem.prep_status == PREP_READY,
        ]

        rows = (
            self.db.query(
                CMSOrderItem.station,
                func.count(CMSOrderItem.id),
                func.coalesce(
                    func.sum(func.timestampdiff(
                        SECONDS, CMSOrder.ordered_at, CMSOrderItem.prep_completed_at
                    )),
                    0,
                ),
            )
            .join(CMSOrder, CMSOrder.id == CMSOrderItem.order_id)
            .filter(*filters)
            .group_by(CMSOrderItem.station)
            .all()
        )

        return [
            {
                "station": station,
                "lines_completed": int(lines or 0),
                "avg_minutes": round((int(seconds or 0) / int(lines or 1)) / 60, 1)
                if lines else 0.0,
            }
            for station, lines, seconds in rows
        ]