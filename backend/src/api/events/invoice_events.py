# from decimal import Decimal
# from sqlalchemy import event
# from sqlalchemy.orm import Session
#
# from src.api.models.hms.invoice_model import Invoice
# from src.api.models.hms.folio_model import Folio
#
#
# # =========================================================
# # SYNC INVOICE FROM FOLIO
# # =========================================================
# def sync_invoice_from_folio(invoice: Invoice):
#     """
#     Copy amounts from folio → invoice
#     """
#     folio = invoice.folio
#
#     if not folio:
#         return
#
#     invoice.total_amount = folio.total_amount or Decimal("0.00")
#     invoice.tax_amount = folio.tax_amount or Decimal("0.00")
#     invoice.discount_amount = folio.discount_amount or Decimal("0.00")
#     invoice.paid_amount = folio.paid_amount or Decimal("0.00")
#
#     # Update calculated fields
#     invoice.update_amounts()
#     invoice.update_payment_status()
#
#
# # =========================================================
# # AUTO SYNC BEFORE FLUSH
# # =========================================================
# @event.listens_for(Session, "before_flush")
# def update_invoice_totals(session: Session, flush_context, instances):
#     """
#     Sync invoice whenever folio changes
#     """
#     affected_invoices = set()
#
#     for obj in session.new.union(session.dirty):
#         # If invoice itself changed
#         if isinstance(obj, Invoice):
#             affected_invoices.add(obj)
#
#         # If folio changed → update its invoice
#         if isinstance(obj, Folio) and obj.invoice:
#             affected_invoices.add(obj.invoice)
#
#     for invoice in affected_invoices:
#         sync_invoice_from_folio(invoice)