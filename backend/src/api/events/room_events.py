from sqlalchemy import event
from src.api.models import Room
from datetime import datetime, timezone



### BEFORE INSERT (Room)
@event.listens_for(Room, "before_insert")
def room_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE UPDATE (Room)
@event.listens_for(Room, "before_update")
def room_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now