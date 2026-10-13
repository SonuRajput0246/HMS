# from decimal import Decimal
# from sqlalchemy import event
# from sqlalchemy.orm import Session
#
# from src.api.models.hms.refund_model import Refund, RefundStatusEnum
# from src.api.models.hms.payment_model import Payment, PaymentStatusEnum
# from src.api.models.hms.folio_model import Folio
#
#
# # =========================================================
# # APPLY REFUND EFFECT
# # =========================================================
# def apply_refund_effect(refund: Refund):
#     """
#     Apply refund impact to payment and folio
#     """
#     if refund.status != RefundStatusEnum.COMPLETED:
#         return
#
#     payment = refund.payment
#     if not payment:
#         return
#
#     # Reduce payment amount impact on folio
#     folio = payment.folio
#     if folio:
#         folio.paid_amount = max(
#             (folio.paid_amount or Decimal("0.00")) - refund.amount,
#             Decimal("0.00")
#         )
#         folio.update_amounts()
#
#     # Update payment status
#     if payment.amount == refund.amount:
#         payment.payment_status = PaymentStatusEnum.REFUNDED
#     elif refund.amount < payment.amount:
#         payment.payment_status = PaymentStatusEnum.SUCCESS
#
#
# # =========================================================
# # AUTO APPLY ON FLUSH
# # =========================================================
# @event.listens_for(Session, "before_flush")
# def handle_refund(session: Session, flush_context, instances):
#     """
#     Automatically handle refund effects before DB flush
#     """
#     for obj in session.new.union(session.dirty):
#         if isinstance(obj, Refund):
#             apply_refund_effect(obj)