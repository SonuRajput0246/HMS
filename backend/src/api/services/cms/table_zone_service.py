from src.api.models.cms.table_zone_model import TableZone
from src.api.models.cms.table_model import Table
from src.api.services.cms.reference_data_helper import revive_or_flag_duplicate
from src.api.utils.responses import service_response


class TableZoneService:
    def __init__(self, db):
        self.db = db

    def get_table_zones(self, data: dict):
        """List zones for the zone picker, ordered for display."""
        page_size = data.get("page_size", 100)
        page_number = data.get("page_number", 1)
        search_value = data.get("search_value")

        query = self.db.query(TableZone).filter(TableZone.is_deleted == False)

        if search_value:
            val = search_value.strip()
            query = query.filter(TableZone.name.like(f"{val}%"))

        total_records = query.count()
        zones = (
            query
            .order_by(TableZone.display_order.asc(), TableZone.id.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        zone_list = [
            {
                "id": zone.id,
                "name": zone.name,
                "display_name": zone.display_name,
                "description": zone.description,
                "display_order": zone.display_order,
                "is_active": zone.is_active
            }
            for zone in zones
        ]

        last_page = (total_records + page_size - 1) // page_size
        return {
            "status": True,
            "data": zone_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_table_zone_by_id(self, zone_id: int):
        zone = self.db.query(TableZone).filter_by(is_deleted=False, id=zone_id).first()
        if not zone:
            return service_response(False, "Table zone not found", None, 404)

        zone_data = {
            "id": zone.id,
            "name": zone.name,
            "display_name": zone.display_name,
            "description": zone.description,
            "display_order": zone.display_order,
            "is_active": zone.is_active
        }
        return service_response(True, "Table zone fetched successfully.", zone_data, 200)

    def upsert_table_zone(self, data: dict):
        zone_id = data["id"]
        zone_name = data["name"]
        is_deleted_op = data.get("is_deleted") is True

        if zone_name and not is_deleted_op:
            duplicate = self.db.query(TableZone).filter(
                TableZone.is_deleted == False,
                TableZone.name == zone_name,
                TableZone.id != zone_id
            ).first()
            if duplicate:
                return service_response(False, "Table zone with this name already exists.", None, 409)

        if zone_id == 0:
            required_fields = ("name", "display_name", "is_active")
            for field in required_fields:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required.", None, 400)

            ## UNIQUE(name) is not partial in MySQL, so a soft-deleted zone
            ## still owns its name and re-adding "Patio" would fail with
            ## IntegrityError 1062. Revive the tombstone and keep its id so any
            ## tables still pointing at it come back with it.
            tombstone, taken = revive_or_flag_duplicate(
                self.db, TableZone, zone_name, zone_id
            )
            if taken:
                return service_response(
                    False, "Table zone with this name already exists.", None, 409
                )

            if tombstone is not None:
                zone = tombstone
                zone.is_deleted = False
                zone.deleted_at = None
                message = "Table zone restored successfully."
            else:
                zone = TableZone()
                self.db.add(zone)
                message = "Table zone created successfully."

            status_code = 201
        else:
            zone = self.db.query(TableZone).filter_by(is_deleted=False, id=zone_id).first()
            if not zone:
                return service_response(False, "Table zone not found", None, 404)

            message = "Table zone updated successfully."
            status_code = 200

        fields = ("name", "display_name", "description", "display_order", "is_active", "is_deleted")
        for field in fields:
            if field in data:
                setattr(zone, field, data[field])

        ## Soft delete must not leave an orphaned gap in the display order, and
        ## more importantly the zone is still referenced by tables. Instead of
        ## blocking the delete, deactivate it: the zone stays resolvable for
        ## historical tables but disappears from the "pick a zone" list.
        if is_deleted_op:
            zone.is_deleted = True
            zone.is_active = False
            message = "Table zone deleted successfully."

        self.db.commit()
        self.db.refresh(zone)

        return service_response(True, message, {"id": zone.id}, status_code)

    def get_zone_table_count(self, zone_id: int):
        """Small helper the zone screen uses to warn before deleting a zone
        that still holds tables."""
        zone = self.db.query(TableZone).filter_by(is_deleted=False, id=zone_id).first()
        if not zone:
            return service_response(False, "Table zone not found", None, 404)

        count = self.db.query(Table).filter(
            Table.is_deleted == False,
            Table.zone_id == zone_id
        ).count()

        return service_response(True, "Fetched table count successfully.", {"table_count": count}, 200)