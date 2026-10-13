from sqlalchemy import event
from datetime import datetime, timezone

from src.api.models.payment_model import Payment


@event.listens_for(Payment, "before_insert")
def payment_before_insert(mapper, connection, target):
    ## created_at / updated_at are nullable=False with no column default, so
    ## without this a direct insert raises MySQLdb.IntegrityError 1048.
    ## verified_at is stamped here rather than by the caller so a payment can
    ## never land with a verification time that disagrees with its row.
    now = datetime.now(timezone.utc)
    target.created_at = now
    target.updated_at = now
    target.verified_at = now