from src.api.models.cms.table_model import Table
from src.api.models.cms.table_zone_model import TableZone
from src.api.models.cms.order_model import CMSOrder, OrderStatusEnum
from src.api.utils.responses import service_response


## Orders in these states still hold the table. A table is only free once the
## order is completed or cancelled, so the POS floor grid stays truthful.
OCCUPYING_ORDER_STATUSES = [
    OrderStatusEnum.PENDING.value,
    OrderStatusEnum.CONFIRMED.value,
    OrderStatusEnum.PREPARING.value,
    OrderStatusEnum.READY.value,
    OrderStatusEnum.SERVED.value,
]


class TableService:
    def __init__(self, db):
        self.db = db

    def get_tables(self, data: dict):
        page_size = data.get("page_size", 100)
        page_number = data.get("page_number", 1)
        zone_id = data.get("zone_id")
        status = data.get("status")
        search_value = data.get("search_value")

        query = self.db.query(Table).filter(Table.is_deleted == False)

        if zone_id:
            query = query.filter(Table.zone_id == zone_id)

        if status:
            query = query.filter(Table.status == status)

        if search_value:
            val = search_value.strip()
            query = query.filter(Table.table_number.like(f"{val}%"))

        total_records = query.count()
        tables = (
            query
            .order_by(Table.table_number.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        table_list = [self._serialize_table(t) for t in tables]

        last_page = (total_records + page_size - 1) // page_size
        return {
            "status": True,
            "data": table_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_table_by_id(self, table_id: int):
        table = self.db.query(Table).filter_by(is_deleted=False, id=table_id).first()
        if not table:
            return service_response(False, "Table not found", None, 404)

        return service_response(True, "Table fetched successfully.", self._serialize_table(table), 200)

    def get_table_floor_view(self):
        """Whole floor at once, grouped by zone.

        The POS screen needs every table with its current order in a single
        paint, so this skips pagination and returns counts per status for the
        header chips.
        """
        tables = (
            self.db.query(Table)
            .filter(Table.is_deleted == False, Table.is_active == True)
            .order_by(Table.table_number.asc())
            .all()
        )

        zones = (
            self.db.query(TableZone)
            .filter(TableZone.is_deleted == False, TableZone.is_active == True)
            .order_by(TableZone.display_order.asc(), TableZone.id.asc())
            .all()
        )

        ## One query for every open order rather than a lazy load per table.
        open_orders = (
            self.db.query(CMSOrder)
            .filter(
                CMSOrder.is_deleted == False,
                CMSOrder.status.in_(OCCUPYING_ORDER_STATUSES)
            )
            .all()
        )
        order_by_table = {}
        for order in open_orders:
            if order.table_id:
                order_by_table[order.table_id] = order

        zone_map = {z.id: z for z in zones}

        grouped = {}
        for table in tables:
            zone = zone_map.get(table.zone_id)
            zone_key = table.zone_id if table.zone_id else 0
            if zone_key not in grouped:
                grouped[zone_key] = {
                    "zone_id": table.zone_id,
                    "zone_name": zone.name if zone else "Unassigned",
                    "zone_display_name": zone.display_name if zone else "Unassigned",
                    "tables": []
                }

            payload = self._serialize_table(table)
            order = order_by_table.get(table.id)
            payload["active_order"] = self._serialize_order_brief(order) if order else None
            grouped[zone_key]["tables"].append(payload)

        counts = {"available": 0, "occupied": 0, "reserved": 0, "cleaning": 0, "maintenance": 0}
        for table in tables:
            if table.status in counts:
                counts[table.status] += 1

        return service_response(
            True,
            "Floor view fetched successfully.",
            {
                "zones": list(grouped.values()),
                "status_counts": counts,
                "total_tables": len(tables)
            },
            200
        )

    def upsert_table(self, data: dict):
        table_id = data["id"]
        table_number = data["table_number"]
        is_deleted_op = data.get("is_deleted") is True

        if table_number and not is_deleted_op:
            duplicate = self.db.query(Table).filter(
                Table.is_deleted == False,
                Table.table_number == table_number,
                Table.id != table_id
            ).first()
            if duplicate:
                return service_response(False, "Table with this number already exists.", None, 409)

        if table_id == 0:
            required_fields = ("table_number", "capacity", "is_active")
            for field in required_fields:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required.", None, 400)

            table = Table()
            self.db.add(table)
            message = "Table created successfully."
            status_code = 201
        else:
            table = self.db.query(Table).filter_by(is_deleted=False, id=table_id).first()
            if not table:
                return service_response(False, "Table not found", None, 404)

            ## Moving or deleting a table that still has an open order would
            ## leave the order pointing at a table nobody can see. Refuse it and
            ## tell the operator to settle the order first.
            if is_deleted_op and self._has_open_order(table_id):
                return service_response(
                    False,
                    "Table cannot be deleted while it has an open order. Close or cancel the order first.",
                    None, 409
                )

            message = "Table updated successfully."
            status_code = 200

        zone_id = data.get("zone_id")
        if zone_id:
            zone = self.db.query(TableZone).filter_by(is_deleted=False, id=zone_id).first()
            if not zone:
                return service_response(False, "Table zone not found", None, 404)

        fields = (
            "table_number", "table_name", "capacity", "zone_id",
            "position_x", "position_y", "shape", "is_combinable",
            "is_active", "is_deleted"
        )
        for field in fields:
            if field in data:
                setattr(table, field, data[field])

        ## status is intentionally NOT in the settable field list above.
        ## On create it stays on the model default; on update a status change
        ## goes through update_table_status so the guard rails there apply.
        if "status" in data and data.get("status"):
            if table.status == "occupied" and data["status"] != "occupied":
                if self._has_open_order(table.id):
                    return service_response(
                        False,
                        "Table is occupied by an open order and cannot be changed manually.",
                        None, 409
                    )
            table.status = data["status"]

        if is_deleted_op:
            table.is_deleted = True
            table.is_active = False
            message = "Table deleted successfully."

        self.db.commit()
        self.db.refresh(table)

        return service_response(True, message, self._serialize_table(table), status_code)

    def update_table_status(self, data: dict):
        """Manual status flip from the table management screen.

        Refuses to release a table that still has an open order, otherwise the
        floor grid would show the table free while a guest is still seated.
        """
        table_id = data["id"]
        new_status = data["status"]

        table = self.db.query(Table).filter_by(is_deleted=False, id=table_id).first()
        if not table:
            return service_response(False, "Table not found", None, 404)

        if new_status != "occupied" and table.status == "occupied" and self._has_open_order(table_id):
            return service_response(
                False,
                "Table has an open order. Close or cancel the order before changing its status.",
                None, 409
            )

        table.status = new_status
        self.db.commit()
        self.db.refresh(table)

        return service_response(
            True, "Table status updated successfully.", self._serialize_table(table), 200
        )

    ## ------------------------------------------------------------------
    ## internals
    ## ------------------------------------------------------------------

    def _has_open_order(self, table_id: int) -> bool:
        return self.db.query(CMSOrder).filter(
            CMSOrder.is_deleted == False,
            CMSOrder.table_id == table_id,
            CMSOrder.status.in_(OCCUPYING_ORDER_STATUSES)
        ).first() is not None

    def _serialize_table(self, table: Table) -> dict:
        return {
            "id": table.id,
            "table_number": table.table_number,
            "table_name": table.table_name,
            "capacity": table.capacity,
            "status": table.status,
            "zone_id": table.zone_id,
            "zone_name": table.zone.name if table.zone else None,
            "position_x": table.position_x,
            "position_y": table.position_y,
            "shape": table.shape,
            "is_combinable": table.is_combinable,
            "is_active": table.is_active
        }

    def _serialize_order_brief(self, order: CMSOrder) -> dict:
        return {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "total_amount": str(order.total_amount),
            "paid_amount": str(order.paid_amount),
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            "item_count": len([i for i in order.items if not i.is_deleted])
        }