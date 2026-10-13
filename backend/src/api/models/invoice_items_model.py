# from decimal import Decimal
#
# from sqlalchemy import (
#     String,
#     Numeric,
#     Integer,
#     ForeignKey,
#     Index,
#     CheckConstraint
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from typing import TYPE_CHECKING
#
# from src.database.base_model import BaseModel
#
#
# if TYPE_CHECKING:
#     from src.api.models.invoice_model import Invoice
#
#
# class InvoiceItem(BaseModel):
#     __tablename__ = "invoice_items"
#
#     # -------------------------
#     # PRIMARY FIELDS
#     # -------------------------
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     invoice_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("invoices.id", ondelete="CASCADE"),
#         nullable=False
#     )
#
#     description: Mapped[str | None] = mapped_column(
#         String(255),
#         nullable=True
#     )
#
#     # -------------------------
#     # PRICING
#     # -------------------------
#     quantity: Mapped[Decimal] = mapped_column(
#         Numeric(10, 2),
#         nullable=False,
#         default=Decimal("1.00")
#     )
#
#     unit_price: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     total_price: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     # -------------------------
#     # RELATIONSHIP
#     # -------------------------
#     invoice: Mapped["Invoice"] = relationship(
#         "Invoice",
#         back_populates="items"
#     )
#
#     # -------------------------
#     # CONSTRAINTS & INDEXES
#     # -------------------------
#     __table_args__ = (
#         CheckConstraint("quantity > 0", name="ck_invoice_item_quantity_positive"),
#         CheckConstraint("unit_price >= 0", name="ck_invoice_item_unit_price_non_negative"),
#         CheckConstraint("total_price >= 0", name="ck_invoice_item_total_price_non_negative"),
#
#         Index("ix_invoice_items_invoice", "is_deleted", "invoice_id", "id"),
#         Index("ix_invoice_items_description", "is_deleted", "description"),
#         Index("ix_invoice_items_total_price", "is_deleted", "total_price", "id"),
#     )
#
#     # =========================================================
#     # METHODS
#     # =========================================================
#     def __repr__(self):
#         return f"InvoiceItem(id={self.id}, description='{self.description}', amount={self.total_price})"
#
#     def calculate_total_price(self) -> Decimal:
#         """Safe calculation"""
#         return (self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
#
#     def update_total_price(self) -> None:
#         """Sync total_price"""
#         self.total_price = self.calculate_total_price()
#
#     def set_description(self, description: str | None) -> None:
#         """Set description safely"""
#         self.description = description.strip() if description else None
#
#     def set_quantity_and_price(self, quantity: Decimal, unit_price: Decimal) -> None:
#         """Set values safely and recalc"""
#         if quantity <= 0:
#             raise ValueError("Quantity must be greater than zero")
#
#         if unit_price < 0:
#             raise ValueError("Unit price cannot be negative")
#
#         self.quantity = quantity
#         self.unit_price = unit_price
#         self.update_total_price()
#
#     def get_formatted_description(self) -> str:
#         return self.description or "Item"
#
#     def get_price_breakdown(self) -> dict:
#         return {
#             "description": self.get_formatted_description(),
#             "quantity": self.quantity,
#             "unit_price": self.unit_price,
#             "total_price": self.total_price,
#         }
#
#     def is_zero_amount(self) -> bool:
#         return self.total_price == Decimal("0.00")
#
#     def copy_from_folio_charge(
#         self,
#         charge_description: str | None,
#         charge_quantity: Decimal,
#         charge_unit_price: Decimal,
#         charge_total_price: Decimal,
#     ) -> None:
#         """Copy data safely from folio charge"""
#         self.description = charge_description
#         self.quantity = charge_quantity
#         self.unit_price = charge_unit_price
#         self.total_price = max(charge_total_price, Decimal("0.00"))