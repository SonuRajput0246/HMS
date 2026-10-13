from decimal import Decimal

from sqlalchemy import func

from src.api.models.cms.order_model import CMSOrder, OrderStatusEnum
from src.api.models.cms.customer_model import Customer
from src.api.services.cms.reports_service import ReportsService, ReportRangeError, _d
from src.api.utils.responses import service_response


ZERO = Decimal("0.00")
SOLD_STATUS = OrderStatusEnum.COMPLETED.value


class CustomerReportService:
    """Regulars, loyalty and retention.

    Lifetime figures come from customers.total_visits / total_spent, which the
    order close path maintains. Period figures are computed from orders inside
    the window. The distinction matters: "who are my regulars" is a
    lifetime question and must not be answered by a 7-day report.
    """

    def __init__(self, db):
        self.db = db

    def get_customer_report(self, data: dict):
        reports = ReportsService(self.db)

        try:
            start, end, from_day, to_day = reports._resolve(data)
        except ReportRangeError as exc:
            return service_response(False, str(exc), None, 400)

        limit = data.get("limit", 20)

        ## Lifetime leaders: the customers who have spent most, ever. This is
        ## the list that should drive a loyalty programme.
        lifetime = (
            self.db.query(
                Customer.id,
                Customer.customer_code,
                Customer.name,
                Customer.phone,
                Customer.loyalty_points,
                Customer.total_visits,
                Customer.total_spent,
                Customer.is_vip,
            )
            .filter(
                Customer.is_deleted == False,
                Customer.is_active == True,
                Customer.total_visits > 0,
            )
            .order_by(Customer.total_spent.desc())
            .limit(limit)
            .all()
        )

        ## Period spend: what these customers did inside the window, so the
        ## owner can see who is currently active rather than historically loyal.
        period_rows = (
            self.db.query(
                CMSOrder.customer_id,
                func.count(CMSOrder.id),
                func.coalesce(func.sum(CMSOrder.total_amount), 0),
            )
            .filter(
                CMSOrder.is_deleted == False,
                CMSOrder.status == SOLD_STATUS,
                CMSOrder.customer_id.isnot(None),
                CMSOrder.completed_at >= start,
                CMSOrder.completed_at < end,
            )
            .group_by(CMSOrder.customer_id)
            .all()
        )

        period_by_customer = {
            cid: {"order_count": int(count or 0), "revenue": _d(value)}
            for cid, count, value in period_rows
        }

        top_customers = []
        for row in lifetime:
            period = period_by_customer.get(row.id, {"order_count": 0, "revenue": ZERO})
            top_customers.append({
                "customer_id": row.id,
                "customer_code": row.customer_code,
                "name": row.name,
                "phone": row.phone,
                "is_vip": row.is_vip,
                "loyalty_points": row.loyalty_points,
                "total_visits": row.total_visits,
                "lifetime_spend": str(_d(row.total_spent)),
                "tier": _tier_for(_d(row.total_spent)),
                "period_order_count": period["order_count"],
                "period_spend": str(period["revenue"]),
            })

        totals = self._totals()
        new_in_period = (
            self.db.query(func.count(Customer.id))
            .filter(
                Customer.is_deleted == False,
                Customer.created_at >= start,
                Customer.created_at < end,
            )
            .scalar()
        ) or 0

        return service_response(
            True,
            "Customer report fetched successfully.",
            {
                "range": reports._range_meta(data, from_day, to_day),
                "totals": totals,
                "new_customers_in_period": int(new_in_period),
                "period_active_customers": len(period_by_customer),
                "top_customers": top_customers,
                "returned": len(top_customers),
            },
            200
        )

    def _totals(self) -> dict:
        """Portfolio-level counts. Cheap aggregate, not a row-by-row scan."""
        row = self.db.query(
            func.count(Customer.id),
            func.coalesce(func.sum(Customer.loyalty_points), 0),
            func.coalesce(func.sum(Customer.total_spent), 0),
            func.coalesce(func.sum(Customer.total_visits), 0),
        ).filter(
            Customer.is_deleted == False,
            Customer.is_active == True,
        ).one()

        total_customers = int(row[0] or 0)
        visits = int(row[3] or 0)
        spend = _d(row[2])

        return {
            "total_customers": total_customers,
            "vip_customers": self.db.query(func.count(Customer.id)).filter(
                Customer.is_deleted == False,
                Customer.is_active == True,
                Customer.is_vip == True,
            ).scalar() or 0,
            "loyalty_points_outstanding": int(row[1] or 0),
            "lifetime_spend": str(spend),
            "total_visits": visits,
            ## Average lifetime value per customer, and per visit.
            "avg_lifetime_value": str(
                (spend / total_customers).quantize(Decimal("0.01")) if total_customers else "0.00"
            ),
            "avg_spend_per_visit": str(
                (spend / visits).quantize(Decimal("0.01")) if visits else "0.00"
            ),
        }


def _tier_for(spend: Decimal) -> str:
    """Mirror of Customer.get_tier, without needing the instance.

    Kept as a module function so a report row can be tiered without loading
    each Customer object.
    """
    if spend >= Customer.PLATINUM_THRESHOLD:
        return "PLATINUM"
    if spend >= Customer.GOLD_THRESHOLD:
        return "GOLD"
    if spend >= Customer.SILVER_THRESHOLD:
        return "SILVER"
    return "REGULAR"