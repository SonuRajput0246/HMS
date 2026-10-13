from sqlalchemy import event
from src.api.models import Guest, AdditionalGuest, ReservationAdditionalGuest
from datetime import datetime, timezone



### BEFORE INSERT (Guest)
@event.listens_for(Guest, "before_insert")
def guest_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE UPDATE (Guest)
@event.listens_for(Guest, "before_update")
def guest_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now

    ## Soft delete handling
    if target.is_deleted:
        if target.deleted_at is None:
            target.deleted_at = now
    else:
        target.deleted_at = None


### BEFORE INSERT (Additional Guest)
@event.listens_for(AdditionalGuest, "before_insert")
def additional_guest_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE INSERT (Reservation Additional Guest)
@event.listens_for(ReservationAdditionalGuest, "before_insert")
def reservation_additional_guest_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
