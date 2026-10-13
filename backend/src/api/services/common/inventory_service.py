from src.api.models import InventoryCategory, Inventory, InventoryUnits
from src.api.utils.responses import service_response


class InventoryService:
    def __init__(self, db):
        self.db = db


    def get_inventory_categories(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = data.get("search_value")
        query = self.db.query(InventoryCategory).filter(InventoryCategory.is_deleted == False)
        if search_value:
            val = search_value.strip()
            query = query.filter(InventoryCategory.name.like(f"{val}%"))
        total_records = query.count()
        inventory_categories = (
            query
            .order_by(InventoryCategory.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )
        inventory_categories_list = [
            {
                "id": inv_cat.id,
                "name": inv_cat.name,
                "description": inv_cat.description,
                "is_active": inv_cat.is_active
            }
            for inv_cat in inventory_categories
        ]
        last_page = (total_records + page_size -1) // page_size
        return {
            "status": True,
            "data": inventory_categories_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_inventory_category_by_id(self, category_id):
            category = self.db.query(InventoryCategory).filter_by(is_deleted=False, id=category_id).first()
            if not category:
                return service_response(False, "Inventory category not found", None, 404)
            inventory_category = {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                    "is_deleted": category.is_deleted
                }
            return service_response(True, "Inventory Category fetched successfully.", inventory_category, 200)


    def upsert_inventory_category(self, data: dict):
        category_id = data["id"]
        category_name = data["name"]

        is_deleted_op = data.get('is_deleted') is True

        if category_name and not is_deleted_op:
            duplicate_check = self.db.query(InventoryCategory).filter(
                InventoryCategory.is_deleted == False,
                InventoryCategory.name == category_name,
                InventoryCategory.id != category_id
            ).first()
            if duplicate_check:
                return service_response(False, "Inventory category with this name already exists.", None, 409)

        if category_id == 0:
            REQUIRED_FIELDS = ("name", "description", "is_active")
            for field in REQUIRED_FIELDS:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required.", None, 400)

            category = InventoryCategory()
            self.db.add(category)
            message = "Inventory Category created successfully."
            status_code = 201
        else:
            category = self.db.query(InventoryCategory).filter_by(is_deleted=False, id=category_id).first()
            if not category:
                return service_response(False, "Inventory category not found", None, 404)

            message = "Inventory category updated successfully."
            status_code = 200

        FIELDS = ("name", "description", "is_active", "is_deleted")
        for field in FIELDS:
            if field in data:
                setattr(category, field, data[field])

        self.db.commit()

        if category.is_deleted:
            message = "Inventory category deleted successfully."

        self.db.commit()
        self.db.refresh(category)
        return service_response(True, message, None, status_code)


    def get_inventories(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = data.get("search_value")
        query = self.db.query(Inventory).join(InventoryCategory).filter(Inventory.is_deleted == False)
        if search_value:
            val = search_value.strip()
            query = query.filter(Inventory.name.like(f"{val}%"))
        total_records = query.count()
        inventories = (
            query
            .order_by(Inventory.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )
        inventory_list = [
            {
                "id": inventory.id,
                "name": inventory.name,
                "category_id": inventory.category_id,
                "category_name": inventory.category.name if inventory.category else None,
                "quantity": inventory.quantity,
                "unit": inventory.unit,
                ## Read by Recipe.calculate_cost_from_ingredients(); the recipe
                ## grid needs it to show what a dish costs to make.
                "unit_cost": (str(inventory.unit_cost)
                              if inventory.unit_cost is not None else None),
                ## Used when an item is rung up directly rather than via a recipe.
                "selling_price": (str(inventory.selling_price)
                                  if inventory.selling_price is not None else None),
                "is_active": inventory.is_active
            }
            for inventory in inventories
        ]
        last_page = (total_records + page_size -1) // page_size
        return {
            "status": True,
            "data": inventory_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200


    def get_inventory_units(self):
        query = self.db.query(InventoryUnits).filter_by(is_active=True)
        records = query.all()
        count = query.count()

        if not records:
            return service_response(False, "Inventory unit not found", None, 404)
        inventory_units_list = [
            {
                "id": inv_unit.id,
                "code": inv_unit.code,
                "label": inv_unit.label
            }
            for inv_unit in records
        ]

        return {
            "status": True,
            "data": inventory_units_list,
            "meta": {
                "current_page": 0,
                "last_page": 0,
                "total_records": count,
                "per_page": 0
            }
        }, 200

    def get_inventory_by_id(self, inventory_id):
        inventory = self.db.query(Inventory).filter_by(is_deleted=False, id=inventory_id).first()
        if not inventory:
            return service_response(False, "Inventory not found", None, 404)
        inventory_data = {
            "id": inventory.id,
            "name": inventory.name,
            "category_id": inventory.category_id,
            "quantity": inventory.quantity,
            "unit": inventory.unit,
            "unit_cost": (str(inventory.unit_cost)
                          if inventory.unit_cost is not None else None),
            "selling_price": (str(inventory.selling_price)
                              if inventory.selling_price is not None else None),
            "is_active": inventory.is_active,
            "is_deleted": inventory.is_deleted
        }
        return service_response(True, "Inventory fetched successfully.", inventory_data, 200)


    def upsert_inventory(self, data: dict):
            inventory_id = data["id"]
            inventory_name = data["name"]
            is_deleted_op = data.get('is_deleted') is True

            if inventory_name and not is_deleted_op:
                duplicate_check = self.db.query(Inventory).filter(
                    Inventory.is_deleted == False,
                    Inventory.name == inventory_name,
                    Inventory.id != inventory_id
                ).first()
                if duplicate_check:
                    return service_response(False, "Inventory with this name already exists.", None, 409)

            if inventory_id == 0:
                REQUIRED_FIELDS = ("name", "category_id", "quantity", "unit", "is_active")
                for field in REQUIRED_FIELDS:
                    if not data.get(field):
                        return service_response(False, f"Field {field} is required." % field, None, 400)

                inventory = Inventory()
                self.db.add(inventory)
                message = "Inventory created successfully."
                status_code = 201
            else:
                inventory = self.db.query(Inventory).filter_by(is_deleted=False, id=inventory_id).first()
                if not inventory:
                    return service_response(False, "Inventory not found", None, 404)

                message = "Inventory updated successfully."
                status_code = 200

            ## unit_cost and selling_price are CMS-facing and are read by
            ## Recipe.calculate_cost_from_ingredients() and by OrderService when
            ## an inventory item is rung up directly. They were missing from this
            ## whitelist, which silently dropped them on every write -- the
            ## schema accepted them and the service then discarded them.
            FIELDS = ("name", "category_id", "quantity", "unit", "unit_cost",
                      "selling_price", "is_active", "is_deleted")
            for field in FIELDS:
                if field in data:
                    setattr(inventory, field, data[field])

            if inventory.is_deleted:
                message = "Inventory deleted successfully."

            self.db.commit()
            self.db.refresh(inventory)
            return service_response(True, message, None, status_code)












