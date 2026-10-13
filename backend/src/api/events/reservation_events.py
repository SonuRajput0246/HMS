from sqlalchemy import event
from src.api.models import ReservationSequence, Reservation, ReservationPrimaryGuest
from datetime import datetime, timezone



### BEFORE INSERT (Reservation Sequence)
@event.listens_for(ReservationSequence, "before_insert")
def reservation_sequence_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE UPDATE (Reservation Sequence)
@event.listens_for(ReservationSequence, "before_update")
def reservation_sequence_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now



### BEFORE INSERT (Reservation)
@event.listens_for(Reservation, "before_insert")
def reservation_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now


### BEFORE UPDATE (Reservation Primary Guest)
@event.listens_for(ReservationPrimaryGuest, "before_insert")
def reservation_primary_guest_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.created_at = now