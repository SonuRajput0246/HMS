# from decimal import Decimal
# from sqlalchemy import event
# from sqlalchemy.orm import Session
# from src.api.models import Folio, FolioCharge, ChargeTypeEnum
#
#
# # =========================================================
# # 1. AUTO CALCULATE TOTAL PRICE (FolioCharge)
# # =========================================================
# @event.listens_for(FolioCharge, "before_insert")
# @event.listens_for(FolioCharge, "before_update")
# def calculate_total_price(mapper, connection, target: FolioCharge):
#     """
#     Automatically calculate total_price before saving
#     """
#     quantity = target.quantity or Decimal("0.00")
#     unit_price = target.unit_price or Decimal("0.00")
#
#     target.total_price = quantity * unit_price
#
#
# # =========================================================
# # 2. SYNC FOLIO TOTALS FUNCTION
# # =========================================================
# def sync_folio_totals(folio: Folio):
#     """
#     Recalculate folio totals from all charges
#     """
#     total = Decimal("0.00")
#     tax = Decimal("0.00")
#     discount = Decimal("0.00")
#
#     for charge in folio.charges:
#         if charge.charge_type == ChargeTypeEnum.TAX:
#             tax += charge.total_price or Decimal("0.00")
#
#         elif charge.charge_type == ChargeTypeEnum.DISCOUNT:
#             discount += charge.total_price or Decimal("0.00")
#
#         else:
#             total += charge.total_price or Decimal("0.00")
#
#     folio.total_amount = total
#     folio.tax_amount = tax
#     folio.discount_amount = discount
#
#     # Update payable + due safely
#     folio.update_amounts()
#
#
# # =========================================================
# # 3. AUTO SYNC BEFORE FLUSH (CORRECT WAY)
# # =========================================================
# @event.listens_for(Session, "before_flush")
# def update_folio_totals(session: Session, flush_context, instances):
#     """
#     Sync folio totals whenever any FolioCharge changes
#     (insert/update/delete safe)
#     """
#     affected_folios = set()
#
#     # Detect all changed FolioCharge objects
#     for obj in session.new.union(session.dirty).union(session.deleted):
#         if isinstance(obj, FolioCharge):
#             if obj.folio:
#                 affected_folios.add(obj.folio)
#
#     # Recalculate totals
#     for folio in affected_folios:
#         sync_folio_totals(folio)