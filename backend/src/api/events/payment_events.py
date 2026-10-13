# from decimal import Decimal
# from sqlalchemy.orm import Session
from src.api.models.payment_model import Payment
from sqlalchemy import event
from datetime import datetime, timezone



### BEFORE INSERT (Payment)
@event.listens_for(Payment, "before_insert")
def payment_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now
    target.verified_at = now



# ### SYNC FOLIO PAID AMOUNT FROM PAYMENTS
# def sync_folio_paid_amount(folio: Folio):
#     """
#     Recalculate folio.paid_amount from successful payments
#     """
#     total_paid = Decimal("0.00")
#
#     for payment in folio.payments:
#         if payment.payment_status == PaymentStatusEnum.SUCCESS:
#             total_paid += payment.amount or Decimal("0.00")
#
#         elif payment.payment_status == PaymentStatusEnum.REFUNDED:
#             total_paid -= payment.amount or Decimal("0.00")
#
#     # Prevent negative
#     folio.paid_amount = max(total_paid, Decimal("0.00"))
#
#     # Update due amount
#     folio.update_amounts()
#
#
# ### AUTO SYNC BEFORE FLUSH (CORRECT WAY)
# @event.listens_for(Session, "before_flush")
# def update_folio_payments(session: Session, flush_context, instances):
#     """
#     Sync folio amounts whenever Payment changes
#     """
#     affected_folios = set()
#
#     for obj in session.new.union(session.dirty).union(session.deleted):
#         if isinstance(obj, Payment) and obj.folio:
#             affected_folios.add(obj.folio)
#
#     for folio in affected_folios:
#         sync_folio_paid_amount(folio)