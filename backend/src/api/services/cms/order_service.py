from decimal import Decimal

from sqlalchemy import or_

from src.api.models.cms.order_model import (
    CMSOrder,
    CMSOrderItem,
    CMSPayment,
    OrderStatusEnum,
    OrderTypeEnum,
    PaymentMethodEnum,
    PaymentStatusEnum,
    PREP_READY,
    PREP_VOIDED,
)
from src.api.utils.datetime_helper import utcnow
from src.api.models.cms.table_model import Table
from src.api.models.cms.customer_model import Customer
from src.api.models.cms.recipe_model import Recipe
from src.api.models.common.inventory_model import Inventory
from src.api.services.common.document_sequence_service import DocumentSequenceService
from src.api.utils.responses import service_response


## Statuses in which an order can still take items, quantity edits or
## cancellations. Once the kitchen has started (preparing) or the bill is
## settled, editing lines silently would desync what the chef is cooking from
## what the guest is charged for.
MUTABLE_ORDER_STATUSES = [
    OrderStatusEnum.PENDING.value,
    OrderStatusEnum.CONFIRMED.value,
]


class OrderService:
    def __init__(self, db):
        self.db = db
        self.sequence_service = DocumentSequenceService(db=db)

    ## ==================================================================
    ## CREATE
    ## ==================================================================

    def create_order(self, data: dict, user_id: int):
        reference_type = data["reference_type"]
        reference_id = data.get("reference_id") or 0

        table = None
        customer = None

        if reference_type == "table":
            table = self.db.query(Table).filter_by(is_deleted=False, id=reference_id).first()
            if not table:
                return service_response(False, "Table not found", None, 404)

            if not table.is_active:
                return service_response(False, "Table is inactive and cannot be used.", None, 409)

            ## A table already running an order cannot be seated again. This is
            ## the single most important guard in the POS: without it a second
            ## waiter could open a second tab on the same table and the two
            ## bills would never meet.
            existing = self.db.query(CMSOrder).filter(
                CMSOrder.is_deleted == False,
                CMSOrder.table_id == table.id,
                CMSOrder.status.in_(MUTABLE_ORDER_STATUSES + [
                    OrderStatusEnum.PREPARING.value,
                    OrderStatusEnum.READY.value,
                    OrderStatusEnum.SERVED.value,
                ])
            ).first()
            if existing:
                return service_response(
                    False,
                    f"Table {table.table_number} already has open order {existing.order_number}.",
                    {"existing_order_id": existing.id, "existing_order_number": existing.order_number},
                    409
                )

            if table.status not in ("available", "reserved"):
                return service_response(
                    False,
                    f"Table {table.table_number} is not available (status: {table.status}).",
                    None, 409
                )

            table.status = "occupied"

        elif reference_type == "customer":
            customer = self.db.query(Customer).filter_by(is_deleted=False, id=reference_id).first()
            if not customer:
                return service_response(False, "Customer not found", None, 404)

        ## reference_type == 'walkin' needs no parent row.

        order = CMSOrder(
            order_number=self.sequence_service.generate("order"),
            reference_type=reference_type,
            reference_id=reference_id,
            table_id=table.id if table else None,
            customer_id=customer.id if customer else None,
            order_type=OrderTypeEnum(data.get("order_type") or OrderTypeEnum.DINE_IN.value),
            tax_amount=Decimal(str(data.get("tax_amount") or 0)),
            discount_amount=Decimal(str(data.get("discount_amount") or 0)),
            notes=data.get("notes"),
            kitchen_notes=data.get("kitchen_notes"),
            created_by=user_id
        )
        ## No items yet, so totals are purely tax/discount. Recomputed by
        ## _recalculate_order on every line change.
        order.calculate_totals()

        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True,
            "Order created successfully.",
            self._serialize_order_detail(order),
            201
        )

    ## ==================================================================
    ## LINE ITEMS
    ## ==================================================================

    def add_item(self, order_id: int, data: dict):
        order = self._get_open_order(order_id)
        if isinstance(order, tuple):
            return order  # already an error (result, code)

        recipe = None
        inventory = None
        unit_price = Decimal("0")
        item_type = None
        item_id = None
        item_name = None
        station = None

        if data.get("recipe_id"):
            recipe = self.db.query(Recipe).filter_by(is_deleted=False, id=data["recipe_id"]).first()
            if not recipe:
                return service_response(False, "Recipe not found", None, 404)

            if not recipe.is_available:
                return service_response(
                    False, f"'{recipe.name}' is currently marked unavailable.", None, 409
                )

            item_type = "recipe"
            item_id = recipe.id
            item_name = recipe.name
            ## Price always comes from the recipe. A client-supplied price on a
            ## recipe line would be a price-tampering hole.
            unit_price = Decimal(str(recipe.selling_price))
            ## Plain string: station values come from the 'recipe_station' enum
            ## definition, not a Python enum, so an admin can add one without a
            ## deploy. Copied verbatim onto the order line.
            station = recipe.station

        else:
            inventory = self.db.query(Inventory).filter_by(is_deleted=False, id=data["inventory_id"]).first()
            if not inventory:
                return service_response(False, "Inventory item not found", None, 404)

            if not inventory.is_active:
                return service_response(False, "Inventory item is inactive.", None, 409)

            item_type = "inventory"
            item_id = inventory.id
            item_name = inventory.name
            station = None

            ## Direct-sell inventory uses selling_price when set; otherwise the
            ## caller may pass a one-off unit_price (a cashier pricing a
            ## takeaway packet by hand).
            if inventory.selling_price is not None:
                unit_price = Decimal(str(inventory.selling_price))
            elif data.get("unit_price") is not None:
                unit_price = Decimal(str(data["unit_price"]))
            else:
                return service_response(
                    False,
                    f"'{inventory.name}' has no selling price. Set one on the item or pass a unit price.",
                    None, 409
                )

            ## Stock guard for direct-sell items only. Recipes are checked
            ## against recipe_ingredients by the stock module, not here, since
            ## one recipe can consume several inventory lines.
            if Decimal(str(inventory.quantity)) <= 0:
                return service_response(
                    False, f"'{inventory.name}' is out of stock.", None, 409
                )

        quantity = Decimal(str(data["quantity"]))

        item = CMSOrderItem(
            order_id=order.id,
            item_type=item_type,
            item_id=item_id,
            item_name=item_name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=quantity * unit_price,
            modifiers=data.get("modifiers"),
            cooking_instructions=data.get("cooking_instructions"),
            spice_level=data.get("spice_level"),
            station=station,
            recipe_id=recipe.id if recipe else None,
            inventory_item_id=inventory.id if inventory else None
        )

        self.db.add(item)
        ## calculate_totals() re-reads order.items, so the new line has to be
        ## flushed and expired first or it will not be in the collection yet.
        self.db.flush()
        self.db.refresh(order)
        self._recalculate_order(order)

        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True,
            "Item added to order successfully.",
            {
                "item_id": item.id,
                "order_id": order.id,
                "subtotal": str(order.subtotal),
                "total_amount": str(order.total_amount)
            },
            201
        )

    def update_item_quantity(self, order_id: int, data: dict):
        order = self._get_open_order(order_id)
        if isinstance(order, tuple):
            return order

        item = self.db.query(CMSOrderItem).filter_by(
            is_deleted=False, id=data["order_item_id"], order_id=order.id
        ).first()
        if not item:
            return service_response(False, "Order item not found", None, 404)

        if item.prep_status == "ready":
            return service_response(
                False,
                "Cannot change quantity of an item the kitchen has already marked ready. Void it instead.",
                None, 409
            )

        item.quantity = Decimal(str(data["quantity"]))
        item.calculate_total()

        self._recalculate_order(order)
        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True,
            "Item quantity updated successfully.",
            {
                "item_id": item.id,
                "subtotal": str(order.subtotal),
                "total_amount": str(order.total_amount)
            },
            200
        )

    def void_item(self, order_id: int, data: dict, user_id: int):
        """Void a line, recording who did it and why.

        user_id comes from the JWT via g.current_user in the route, never from
        the request body -- otherwise a client could void a line and attribute
        it to a colleague.
        """
        order = self._get_open_order(order_id)
        if isinstance(order, tuple):
            return order

        item = self.db.query(CMSOrderItem).filter_by(
            is_deleted=False, id=data["order_item_id"], order_id=order.id
        ).first()
        if not item:
            return service_response(False, "Order item not found", None, 404)

        if item.prep_status == "ready":
            return service_response(
                False,
                "Cannot void an item the kitchen has already marked ready.",
                None, 409
            )

        ## Soft delete so the void stays auditable, with reason, actor and
        ## timestamp on their own columns rather than smuggled into
        ## cooking_instructions -- the loss report filters and groups on these,
        ## and the kitchen still needs that field clean for the dish.
        item.is_deleted = True
        item.prep_status = PREP_VOIDED
        item.void_reason = data["reason"]
        item.voided_at = utcnow()
        item.voided_by = user_id

        self._recalculate_order(order)
        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True,
            "Item voided successfully.",
            {
                "item_id": item.id,
                "subtotal": str(order.subtotal),
                "total_amount": str(order.total_amount)
            },
            200
        )

    ## ==================================================================
    ## STATUS FLOW
    ## ==================================================================

    def update_status(self, order_id: int, data: dict):
        order = self._get_order_or_404(order_id)
        if isinstance(order, tuple):
            return order

        target = data["status"]
        current = order.status

        ## Delegated to the model so the legal transitions live in one place.
        transition = {
            OrderStatusEnum.CONFIRMED.value: order.confirm,
            OrderStatusEnum.PREPARING.value: order.start_preparing,
            OrderStatusEnum.READY.value: order.mark_ready,
            OrderStatusEnum.SERVED.value: order.serve,
        }.get(target)

        if not transition:
            return service_response(False, f"Cannot set order status to '{target}'.", None, 400)

        if current in (OrderStatusEnum.COMPLETED, OrderStatusEnum.CANCELLED):
            return service_response(
                False, f"Order is already {current} and its status cannot change.", None, 409
            )

        try:
            transition()
        except ValueError as exc:
            return service_response(False, str(exc), None, 409)

        ## The header may only reach 'ready' once every live line is ready.
        ## The KDS advances lines one at a time, so without this the waiter
        ## would see the whole ticket marked ready while two plates are still
        ## on the pass. Roll the header back to preparing in that case.
        if target == OrderStatusEnum.READY.value:
            not_ready = self.db.query(CMSOrderItem).filter(
                CMSOrderItem.order_id == order.id,
                CMSOrderItem.is_deleted == False,
                CMSOrderItem.prep_status.notin_([PREP_READY, PREP_VOIDED])
            ).count()
            if not_ready:
                order.status = OrderStatusEnum.PREPARING

        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True, "Order status updated successfully.", self._serialize_order_brief(order), 200
        )

    def cancel_order(self, order_id: int, data: dict, user_id: int):
        order = self._get_order_or_404(order_id)
        if isinstance(order, tuple):
            return order

        if order.is_fully_paid():
            return service_response(
                False,
                "Order is already paid. Raise a refund instead of cancelling.",
                None, 409
            )

        try:
            order.cancel(reason=data["reason"], user_id=user_id)
        except ValueError as exc:
            return service_response(False, str(exc), None, 409)

        ## Cancel the whole ticket in the kitchen too, otherwise the chef keeps
        ## cooking food nobody will pay for. Stamped as a void so the loss
        ## report counts cancelled lines alongside cashier voids.
        self.db.query(CMSOrderItem).filter(
            CMSOrderItem.order_id == order.id,
            CMSOrderItem.is_deleted == False
        ).update(
            {
                "prep_status": PREP_VOIDED,
                "void_reason": f"Order cancelled: {data['reason']}",
                "voided_at": utcnow(),
                "voided_by": user_id,
            },
            synchronize_session=False,
        )

        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True, "Order cancelled successfully.", self._serialize_order_brief(order), 200
        )

    ## ==================================================================
    ## PAYMENT
    ## ==================================================================

    def process_payment(self, order_id: int, data: dict, user_id: int):
        """Record one payment.

        A split bill is several calls that share a split_group_id. Overpayment
        is rejected rather than absorbed, because accepting a tip as an
        overpayment would silently change what change the cashier hands back.
        """
        order = self._get_order_or_404(order_id)
        if isinstance(order, tuple):
            return order

        if order.status in (OrderStatusEnum.COMPLETED, OrderStatusEnum.CANCELLED):
            return service_response(
                False, f"Cannot take payment on a {order.status} order.", None, 409
            )

        amount = Decimal(str(data["amount"]))
        due = order.due_amount()

        if due <= 0:
            return service_response(False, "Order is already fully paid.", None, 409)

        if amount > due:
            return service_response(
                False,
                f"Payment of {amount} exceeds the outstanding balance of {due}.",
                None, 400
            )

        payment = CMSPayment(
            order_id=order.id,
            amount=amount,
            payment_method=PaymentMethodEnum(data["payment_method"]),
            payment_status=PaymentStatusEnum.PAID,
            split_group_id=data.get("split_group_id"),
            split_payer_name=data.get("split_payer_name"),
            transaction_ref=data.get("transaction_ref"),
            remarks=data.get("remarks"),
            created_by=user_id
        )
        payment.mark_success(
            transaction_ref=data.get("transaction_ref"),
            verified_by=user_id
        )

        self.db.add(payment)

        order.paid_amount = order.paid_amount + amount
        order.update_payment_status()

        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True,
            "Payment processed successfully.",
            {
                "payment_id": payment.id,
                "order_id": order.id,
                "paid_amount": str(order.paid_amount),
                "total_amount": str(order.total_amount),
                "due_amount": str(order.due_amount()),
                "payment_status": order.payment_status.value
            },
            201
        )

    def close_order(self, order_id: int, data: dict, user_id: int):
        """Close the order: free the table, bank the loyalty visit.

        complete_payment=True takes the remaining balance first, which is the
        common "settle and close" path from the till.
        """
        order = self._get_order_or_404(order_id)
        if isinstance(order, tuple):
            return order

        if order.status == OrderStatusEnum.CANCELLED:
            return service_response(False, "Order is cancelled and cannot be closed.", None, 409)

        if order.status == OrderStatusEnum.COMPLETED:
            return service_response(False, "Order is already closed.", None, 409)

        if data.get("complete_payment"):
            due = order.due_amount()
            if due > Decimal("0"):
                method = data.get("payment_method") or PaymentMethodEnum.CASH.value
                payment = CMSPayment(
                    order_id=order.id,
                    amount=due,
                    payment_method=PaymentMethodEnum(method),
                    payment_status=PaymentStatusEnum.PAID,
                    transaction_ref=data.get("transaction_ref"),
                    created_by=user_id
                )
                payment.mark_success(
                    transaction_ref=data.get("transaction_ref"),
                    verified_by=user_id
                )
                self.db.add(payment)
                order.paid_amount = order.paid_amount + due
                order.update_payment_status()

        if not order.is_fully_paid():
            due = order.due_amount()
            return service_response(
                False,
                f"Order has an outstanding balance of {due}. Take payment before closing.",
                None, 409
            )

        ## complete() refuses if unpaid, and frees the table + records the
        ## customer visit as a side effect.
        order.complete()
        self.db.commit()
        self.db.refresh(order)

        return service_response(
            True,
            "Order closed successfully.",
            self._serialize_order_detail(order),
            200
        )

    ## ==================================================================
    ## READS
    ## ==================================================================

    def get_order(self, order_id: int):
        order = self._get_order_or_404(order_id)
        if isinstance(order, tuple):
            return order

        return service_response(
            True, "Order fetched successfully.", self._serialize_order_detail(order), 200
        )

    def get_orders(self, data: dict):
        page_size = data.get("page_size", 20)
        page_number = data.get("page_number", 1)

        query = self.db.query(CMSOrder).filter(CMSOrder.is_deleted == False)

        for field in ("status", "payment_status", "table_id", "customer_id"):
            value = data.get(field)
            if value:
                query = query.filter(getattr(CMSOrder, field) == value)

        if data.get("from_date"):
            query = query.filter(CMSOrder.ordered_at >= data["from_date"])
        if data.get("to_date"):
            query = query.filter(CMSOrder.ordered_at <= data["to_date"])

        if data.get("search_value"):
            val = data["search_value"].strip()
            ## Order number substring, plus an exact hit on reference_id when
            ## the operator typed digits (tapping a table/customer by id).
            if val.isdigit():
                query = query.filter(
                    or_(CMSOrder.order_number.like(f"%{val}%"), CMSOrder.reference_id == int(val))
                )
            else:
                query = query.filter(CMSOrder.order_number.like(f"%{val}%"))

        total_records = query.count()
        orders = (
            query
            .order_by(CMSOrder.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        last_page = (total_records + page_size - 1) // page_size
        return {
            "status": True,
            "data": [self._serialize_order_brief(o) for o in orders],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_table_active_order(self, table_id: int):
        """What the POS shows when a waiter taps an occupied table."""
        table = self.db.query(Table).filter_by(is_deleted=False, id=table_id).first()
        if not table:
            return service_response(False, "Table not found", None, 404)

        order = (
            self.db.query(CMSOrder)
            .filter(
                CMSOrder.is_deleted == False,
                CMSOrder.table_id == table_id,
                CMSOrder.status.notin_([
                    OrderStatusEnum.COMPLETED.value,
                    OrderStatusEnum.CANCELLED.value,
                ])
            )
            .order_by(CMSOrder.id.desc())
            .first()
        )
        if not order:
            return service_response(False, "No active order for this table.", None, 404)

        return service_response(
            True, "Active order fetched successfully.", self._serialize_order_detail(order), 200
        )

    ## ==================================================================
    ## internals
    ## ==================================================================

    def _get_order_or_404(self, order_id: int):
        order = self.db.query(CMSOrder).filter_by(is_deleted=False, id=order_id).first()
        if not order:
            return service_response(False, "Order not found", None, 404)
        return order

    def _get_open_order(self, order_id: int):
        """Fetch an order that is still allowed to be edited."""
        order = self._get_order_or_404(order_id)
        if isinstance(order, tuple):
            return order

        if order.status not in MUTABLE_ORDER_STATUSES:
            return service_response(
                False,
                f"Order is '{order.status}' and its items can no longer be changed. Void the order instead.",
                None, 409
            )

        return order

    def _recalculate_order(self, order: CMSOrder) -> None:
        """Recompute subtotal/total after a line change.

        Calls calculate_totals() on the model, which sums the live items
        collection, then keeps payment_status consistent with paid_amount.
        """
        order.calculate_totals()
        order.update_payment_status()

    def _serialize_order_brief(self, order: CMSOrder) -> dict:
        active_items = [i for i in order.items if not i.is_deleted]
        return {
            "id": order.id,
            "order_number": order.order_number,
            "reference_type": order.reference_type,
            "reference_id": order.reference_id,
            "reference_label": order.get_reference_label(),
            "table_id": order.table_id,
            "customer_id": order.customer_id,
            "status": order.status.value,
            "order_type": order.order_type.value,
            "subtotal": str(order.subtotal),
            "tax_amount": str(order.tax_amount),
            "discount_amount": str(order.discount_amount),
            "total_amount": str(order.total_amount),
            "payment_status": order.payment_status.value,
            "paid_amount": str(order.paid_amount),
            "due_amount": str(order.due_amount()),
            "item_count": len(active_items),
            "notes": order.notes,
            "kitchen_notes": order.kitchen_notes,
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            "completed_at": order.completed_at.isoformat() if order.completed_at else None
        }

    def _serialize_order_detail(self, order: CMSOrder) -> dict:
        payload = self._serialize_order_brief(order)

        payload["items"] = [
            {
                "id": item.id,
                "item_type": item.item_type,
                "item_id": item.item_id,
                "item_name": item.item_name,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "total_price": str(item.total_price),
                "modifiers": item.modifiers,
                "cooking_instructions": item.cooking_instructions,
                "spice_level": item.spice_level,
                "prep_status": item.prep_status,
                "station": item.station,
                "recipe_id": item.recipe_id,
                "inventory_item_id": item.inventory_item_id
            }
            for item in order.items if not item.is_deleted
        ]

        payload["payments"] = [
            {
                "id": p.id,
                "amount": str(p.amount),
                "payment_method": p.payment_method.value,
                "payment_status": p.payment_status.value,
                "split_group_id": p.split_group_id,
                "split_payer_name": p.split_payer_name,
                "transaction_ref": p.transaction_ref,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "remarks": p.remarks
            }
            for p in order.payments if not p.is_deleted
        ]

        if order.table:
            payload["table"] = {
                "id": order.table.id,
                "table_number": order.table.table_number,
                "table_name": order.table.table_name,
                "zone_name": order.table.zone.name if order.table.zone else None
            }

        if order.customer:
            payload["customer"] = {
                "id": order.customer.id,
                "customer_code": order.customer.customer_code,
                "name": order.customer.name,
                "phone": order.customer.phone,
                "loyalty_points": order.customer.loyalty_points,
                "tier": order.customer.get_tier()
            }

        return payload