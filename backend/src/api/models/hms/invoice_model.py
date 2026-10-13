# from decimal import Decimal
# from enum import Enum
# from datetime import datetime
#
# from sqlalchemy import (
#     Enum as SqlEnum,
#     String,
#     Numeric,
#     Integer,
#     ForeignKey,
#     DateTime,
#     Index
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from sqlalchemy.sql import func
# from typing import TYPE_CHECKING
#
# from src.database.base_model import BaseModel
#
#
# if TYPE_CHECKING:
#     from src.api.models.hms.folio_model import Folio
#     from src.api.models.hms.invoice_items_model import InvoiceItem
#
#
# # =========================================================
# # ENUM
# # =========================================================
# class InvoicePaymentStatusEnum(str, Enum):
#     UNPAID = "unpaid"
#     PARTIAL = "partial"
#     PAID = "paid"
#
#
# # =========================================================
# # MODEL
# # =========================================================
# class Invoice(BaseModel):
#     __tablename__ = "invoices"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     folio_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("folios.id", ondelete="CASCADE"),
#         nullable=False
#     )
#
#     invoice_number: Mapped[str] = mapped_column(
#         String(50),
#         nullable=False,
#         unique=True
#     )
#
#     # -------------------------
#     # AMOUNTS
#     # -------------------------
#     total_amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     tax_amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     discount_amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     final_amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     paid_amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     due_amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     payment_status: Mapped[InvoicePaymentStatusEnum] = mapped_column(
#         SqlEnum(InvoicePaymentStatusEnum),
#         nullable=False,
#         default=InvoicePaymentStatusEnum.UNPAID
#     )
#     creat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
#
#     # -------------------------
#     # METADATA
#     # -------------------------
#     generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
#
#     pdf_path: Mapped[str | None] = mapped_column(
#         String(255),
#         nullable=True
#     )
#
#     # -------------------------
#     # RELATIONSHIP
#     # -------------------------
#     folio: Mapped["Folio"] = relationship(
#         "Folio",
#         back_populates="invoice"
#     )
#     items: Mapped[list["InvoiceItem"]] = relationship(
#         "InvoiceItem",
#         back_populates="invoice",
#         cascade="all, delete-orphan"
#     )
#
#     # -------------------------
#     # INDEXES
#     # -------------------------
#     __table_args__ = (
#         Index("ix_invoice_folio", "is_deleted", "folio_id", "id"),
#         Index("ix_invoice_payment_status", "is_deleted", "payment_status", "id"),
#         Index("ix_invoice_number", "is_deleted", "invoice_number"),
#         Index("ix_invoice_generated_at", "is_deleted", "generated_at", "id"),
#     )
#
#     # =========================================================
#     # METHODS
#     # =========================================================
#     def __repr__(self):
#         return f"Invoice(id={self.id}, number='{self.invoice_number}', status='{self.payment_status}', amount={self.final_amount})"
#
#     def calculate_final_amount(self) -> Decimal:
#         """total + tax - discount (safe)"""
#         return max(
#             self.total_amount + self.tax_amount - self.discount_amount,
#             Decimal("0.00")
#         )
#
#     def calculate_due_amount(self) -> Decimal:
#         """final - paid (safe)"""
#         return max(
#             self.final_amount - self.paid_amount,
#             Decimal("0.00")
#         )
#
#     def update_amounts(self) -> None:
#         """sync final + due"""
#         self.final_amount = self.calculate_final_amount()
#         self.due_amount = self.calculate_due_amount()
#
#     def update_payment_status(self) -> None:
#         """sync status"""
#         if self.due_amount <= Decimal("0.00"):
#             self.payment_status = InvoicePaymentStatusEnum.PAID
#         elif self.paid_amount > Decimal("0.00"):
#             self.payment_status = InvoicePaymentStatusEnum.PARTIAL
#         else:
#             self.payment_status = InvoicePaymentStatusEnum.UNPAID
#
#     def add_payment(self, amount: Decimal) -> None:
#         """add payment safely"""
#         if amount <= 0:
#             raise ValueError("Payment amount must be positive")
#
#         self.paid_amount += amount
#         self.update_amounts()
#         self.update_payment_status()
#
#     # -------------------------
#     # STATUS HELPERS
#     # -------------------------
#     def is_unpaid(self) -> bool:
#         return self.payment_status == InvoicePaymentStatusEnum.UNPAID
#
#     def is_partially_paid(self) -> bool:
#         return self.payment_status == InvoicePaymentStatusEnum.PARTIAL
#
#     def is_fully_paid(self) -> bool:
#         return self.payment_status == InvoicePaymentStatusEnum.PAID
#
#     # -------------------------
#     # UTILITIES
#     # -------------------------
#     def has_pdf(self) -> bool:
#         return self.pdf_path is not None and self.pdf_path.strip() != ""
#
#     def set_pdf_path(self, path: str) -> None:
#         self.pdf_path = path
#
#     def can_be_deleted(self) -> bool:
#         return self.is_unpaid() and self.paid_amount == Decimal("0.00")
#
#     def get_amount_breakdown(self) -> dict:
#         return {
#             "total_amount": self.total_amount,
#             "tax_amount": self.tax_amount,
#             "discount_amount": self.discount_amount,
#             "final_amount": self.final_amount,
#             "paid_amount": self.paid_amount,
#             "due_amount": self.due_amount,
#         }