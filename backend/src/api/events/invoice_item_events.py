# from decimal import Decimal
# from sqlalchemy import event
#
# from src.api.models import InvoiceItem
#
#
# # =========================================================
# # AUTO CALCULATE TOTAL PRICE
# # =========================================================
# @event.listens_for(InvoiceItem, "before_insert")
# @event.listens_for(InvoiceItem, "before_update")
# def calculate_total_price(mapper, connection, target: InvoiceItem):
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
# # VALIDATE DATA
# # =========================================================
# @event.listens_for(InvoiceItem, "before_insert")
# @event.listens_for(InvoiceItem, "before_update")
# def validate_invoice_item(mapper, connection, target: InvoiceItem):
#     """
#     Validate invoice item before saving
#     """
#
#     if target.quantity is None or target.quantity <= 0:
#         raise ValueError("Quantity must be greater than zero")
#
#     if target.unit_price is None or target.unit_price < 0:
#         raise ValueError("Unit price cannot be negative")
#
#     if target.total_price is not None and target.total_price < 0:
#         raise ValueError("Total price cannot be negative")