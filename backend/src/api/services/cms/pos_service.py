from datetime import datetime, time as dt_time
from decimal import Decimal

from src.api.models.cms.order_model import (
    CMSOrder,
    CMSPayment,
    OrderStatusEnum,
    PaymentStatusEnum,
    PREP_READY,
    PREP_VOIDED,
)
from src.api.models.cms.table_model import Table
from src.api.utils.datetime_helper import utcnow
from src.api.utils.responses import service_response


class PosService:
    """Point of Sale.

    Deliberately thin. Creating orders, adding lines, taking payment and closing
    all live in OrderService, which owns those rules -- duplicating them here
    would give the till and the order history two different definitions of
    "paid". What this adds is the read model the till needs: the bill, and the
    landing-screen counters.
    """

    def __init__(self, db):
        self.db = db

    ## ==================================================================
    ## READS
    ## ==================================================================

    def get_bill(self, data: dict):
        """The bill / receipt for one order.

        A pure read: rendering a bill must never be able to move money. It also
        computes what the cashier still needs to collect, and whether the order
        is closeable, so the till screen needs one round trip instead of two.
        """
        order_id = data["order_id"]

        order = self.db.query(CMSOrder).filter_by(is_deleted=False, id=order_id).first()
        if not order:
            return service_response(False, "Order not found", None, 404)

        include_tax_breakup = data.get("include_tax_breakup", True)

        ## Recompute rather than trusting the header. The header is authoritative
        ## once the order is closed, but while it is open a concurrent add-item
        ## call may have moved the lines on without the header being refreshed
        ## in this session, and a receipt that disagrees with the till is worse
        ## than a few milliseconds of arithmetic.
        live_items = [i for i in order.items if not i.is_deleted]

        item_subtotal = Decimal("0.00")
        for item in live_items:
            item_subtotal += item.total_price

        tax = order.tax_amount or Decimal("0.00")
        discount = order.discount_amount or Decimal("0.00")
        total = item_subtotal + tax - discount
        if total < Decimal("0.00"):
            total = Decimal("0.00")

        paid = Decimal("0.00")
        payments = []
        for payment in order.payments:
            if payment.is_deleted or payment.payment_status != PaymentStatusEnum.PAID:
                continue
            paid += payment.amount
            payments.append({
                "id": payment.id,
                "amount": str(payment.amount),
                "payment_method": payment.payment_method.value,
                "transaction_ref": payment.transaction_ref,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                "split_payer_name": payment.split_payer_name
            })

        due = max(total - paid, Decimal("0.00"))

        payload = {
            "order_id": order.id,
            "order_number": order.order_number,
            "order_status": order.status.value,
            "order_type": order.order_type.value,
            "reference_label": order.get_reference_label(),
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            "completed_at": order.completed_at.isoformat() if order.completed_at else None,

            "table": self._serialize_table(order.table),
            "customer": self._serialize_customer(order.customer),

            "items": [
                {
                    "id": i.id,
                    "item_name": i.item_name,
                    "quantity": str(i.quantity),
                    "unit_price": str(i.unit_price),
                    "total_price": str(i.total_price),
                    "modifiers": i.modifiers,
                    "prep_status": i.prep_status,
                    "cooking_instructions": i.cooking_instructions,
                    "spice_level": i.spice_level
                }
                for i in live_items
            ],

            "totals": {
                "item_subtotal": str(item_subtotal),
                "tax_amount": str(tax),
                "discount_amount": str(discount),
                "total_amount": str(total),
                "paid_amount": str(paid),
                "due_amount": str(due)
            },

            "payments": payments,
            "payment_count": len(payments),

            ## Derived flags so the till renders the right buttons without
            ## re-deriving the rules client-side.
            "is_fully_paid": due == Decimal("0.00") and total > Decimal("0.00"),
            "is_closable": due == Decimal("0.00") and order.status != OrderStatusEnum.COMPLETED,
            "kitchen_outstanding": self._kitchen_outstanding(live_items),

            "generated_at": utcnow().isoformat()
        }

        if include_tax_breakup:
            payload["tax_breakup"] = self._tax_breakup(item_subtotal, tax, discount)

        return service_response(True, "Bill fetched successfully.", payload, 200)

    def get_summary(self, data: dict):
        """Landing-screen counters for the till.

        Occupancy from the tables (not from orders) because a table is the thing
        a waiter acts on, and revenue from today's settled orders only -- cash
        taken so far today, not the sum of every open bill.
        """
        include_today_revenue = data.get("include_today_revenue", True)

        status_rows = (
            self.db.query(Table.status, Table.id)
            .filter(Table.is_deleted == False, Table.is_active == True)
            .all()
        )
        table_counts = {"available": 0, "occupied": 0, "reserved": 0, "cleaning": 0, "maintenance": 0}
        for status, _ in status_rows:
            if status in table_counts:
                table_counts[status] += 1

        open_orders = self.db.query(CMSOrder).filter(
            CMSOrder.is_deleted == False,
            CMSOrder.status.notin_([
                OrderStatusEnum.COMPLETED.value,
                OrderStatusEnum.CANCELLED.value,
            ])
        ).count()

        payload = {
            "tables": {
                "total": len(status_rows),
                **table_counts
            },
            "open_orders": open_orders,
            "generated_at": utcnow().isoformat()
        }

        if include_today_revenue:
            ## cms_orders.completed_at is a MySQL DATETIME and therefore comes
            ## back NAIVE, so the bound has to be naive UTC too or the
            ## comparison raises "can't subtract offset-naive and offset-aware".
            start_of_day = datetime.combine(utcnow().date(), dt_time.min)
            settled = (
                self.db.query(CMSOrder)
                .filter(
                    CMSOrder.is_deleted == False,
                    CMSOrder.status == OrderStatusEnum.COMPLETED.value,
                    CMSOrder.completed_at >= start_of_day
                )
                .all()
            )
            revenue = Decimal("0.00")
            for order in settled:
                revenue += order.total_amount or Decimal("0.00")

            payload["today"] = {
                "completed_orders": len(settled),
                "revenue": str(revenue),
                "average_ticket": str(
                    (revenue / len(settled)).quantize(Decimal("0.01")) if settled else "0.00"
                )
            }

        return service_response(True, "Summary fetched successfully.", payload, 200)

    ## ==================================================================
    ## internals
    ## ==================================================================

    def _kitchen_outstanding(self, items) -> int:
        """How many lines the kitchen has not plated yet."""
        return len([
            i for i in items
            if not i.is_deleted
            and i.prep_status not in (PREP_READY, PREP_VOIDED)
        ])

    def _tax_breakup(self, item_subtotal: Decimal, tax: Decimal, discount: Decimal):
        """Split the total back into taxable base and tax portion.

        Derived rather than stored: GST rules restate an amount as
        base + tax, and computing it keeps one source of truth instead of a
        stored column that can disagree with tax_amount.
        """
        base_after_discount = max(item_subtotal - discount, Decimal("0.00"))

        if tax <= Decimal("0.00") or base_after_discount <= Decimal("0.00"):
            return {
                "taxable_amount": str(base_after_discount),
                "tax_amount": str(tax),
                "total_with_tax": str(base_after_discount + tax),
                "effective_rate_percent": "0.00"
            }

        ## tax / (base + tax) recovers the rate from the inclusive total.
        inclusive = base_after_discount + tax
        rate = (tax / inclusive) * Decimal("100")

        return {
            "taxable_amount": str(base_after_discount),
            "tax_amount": str(tax),
            "total_with_tax": str(inclusive),
            "effective_rate_percent": str(rate.quantize(Decimal("0.01")))
        }

    def _serialize_table(self, table) -> dict | None:
        if not table:
            return None
        return {
            "id": table.id,
            "table_number": table.table_number,
            "table_name": table.table_name,
            "capacity": table.capacity,
            "status": table.status,
            "zone_id": table.zone_id,
            "zone_name": table.zone.name if table.zone else None
        }

    def _serialize_customer(self, customer) -> dict | None:
        if not customer:
            return None
        return {
            "id": customer.id,
            "customer_code": customer.customer_code,
            "name": customer.name,
            "phone": customer.phone,
            "loyalty_points": customer.loyalty_points,
            "tier": customer.get_tier()
        }