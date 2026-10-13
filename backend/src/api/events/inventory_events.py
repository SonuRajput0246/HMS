from sqlalchemy import event
from datetime import datetime, timezone
from src.api.models.inventory_category_model import InventoryCategory
from src.api.models.inventory_model import Inventory



### BEFORE INSERT (Inventory Category)
@event.listens_for(InventoryCategory, "before_insert")
def inventory_category_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE Update (Inventory Category)
@event.listens_for(InventoryCategory, "before_update")
def inventory_category_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now

    ## Soft delete handling
    if target.is_deleted and target.deleted_at is None:
        target.deleted_at = now



### BEFORE INSERT (Inventory)
@event.listens_for(Inventory, "before_insert")
def inventory_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE Update (Inventory)
@event.listens_for(Inventory, "before_update")
def inventory_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now

    ## Soft delete handling
    if target.is_deleted and target.deleted_at is None:
        target.deleted_at = now








