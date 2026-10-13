# from decimal import Decimal
# from enum import Enum
# from datetime import datetime
#
# from sqlalchemy import (
#     Enum as SqlEnum,
#     String,
#     Numeric,
#     CheckConstraint,
#     Integer,
#     ForeignKey,
#     DateTime,
#     Index,
#     text
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from sqlalchemy.sql import func
# from typing import TYPE_CHECKING
#
# from src.database.base_model import BaseModel
#
# if TYPE_CHECKING:
#     # Only for type hints (avoids circular imports)
#     from src.api.models.reservation_model import Reservation
#     from src.api.models.user_model import User
#     from src.api.models.guest_model import Guest
#     from src.api.models.folio_charges_model import FolioCharge
#     from src.api.models.payment_model import Payment
#     from src.api.models.invoice_model import Invoice
#
#
# # =========================================================
# # ENUM
# # =========================================================
# class FolioStatusEnum(str, Enum):
#     OPEN = "OPEN"
#     CLOSED = "CLOSED"
#     CANCELLED = "CANCELLED"
#
#
# # =========================================================
# # MODEL
# # =========================================================
# class Folio(BaseModel):
#     __tablename__ = "folios"
#
#     # -------------------------
#     # PRIMARY FIELDS
#     # -------------------------
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     reservation_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("reservations.id", ondelete="CASCADE"),
#         nullable=False
#     )
#
#     guest_id: Mapped[int | None] = mapped_column(
#         Integer,
#         ForeignKey("guests.id", ondelete="CASCADE"),
#         nullable=True
#     )
#
#     folio_number: Mapped[str] = mapped_column(
#         String(50),
#         nullable=False,
#         unique=True
#     )
#
#     status: Mapped[FolioStatusEnum] = mapped_column(
#         SqlEnum(FolioStatusEnum),
#         nullable=False,
#         default=FolioStatusEnum.OPEN
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
#     payable_amount: Mapped[Decimal] = mapped_column(
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
#     currency: Mapped[str] = mapped_column(
#         String(10),
#         nullable=False,
#         default="INR"
#     )
#
#     # -------------------------
#     # TIMESTAMPS
#     # -------------------------
#     opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
#
#     closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
#
#     # -------------------------
#     # AUDIT
#     # -------------------------
#     created_by: Mapped[int | None] = mapped_column(
#         ForeignKey("users.id"),
#         nullable=True
#     )
#
#     version: Mapped[int] = mapped_column(
#         default=1,
#         nullable=False
#     )
#
#     # -------------------------
#     # RELATIONSHIPS
#     # -------------------------
#     guest: Mapped["Guest | None"] = relationship(
#         "Guest",
#         back_populates="folios"
#     )
#
#     charges: Mapped[list["FolioCharge"]] = relationship(
#         "FolioCharge",
#         back_populates="folio",
#         cascade="all, delete-orphan"
#     )
#
#     reservation: Mapped["Reservation"] = relationship(
#         "Reservation",
#         back_populates="folios"
#     )
#
#     payments: Mapped[list["Payment"]] = relationship(
#         "Payment",
#         back_populates="folio",
#         cascade="all, delete-orphan"
#     )
#
#     invoice: Mapped["Invoice | None"] = relationship(
#         "Invoice",
#         back_populates="folio",
#         uselist=False
#     )
#
#     created_by_user: Mapped["User | None"] = relationship(
#         "User"
#     )
#
#     # -------------------------
#     # VERSIONING (Optimistic Locking)
#     # -------------------------
#     __mapper_args__ = {
#         "version_id_col": version
#     }
#
#     # -------------------------
#     # CONSTRAINTS & INDEXES
#     # -------------------------
#     __table_args__ = (
#         CheckConstraint("total_amount >= 0", name="ck_total_amount_non_negative"),
#         CheckConstraint("tax_amount >= 0", name="ck_tax_amount_non_negative"),
#         CheckConstraint("discount_amount >= 0", name="ck_discount_amount_non_negative"),
#         CheckConstraint("payable_amount >= 0", name="ck_payable_amount_non_negative"),
#         CheckConstraint("paid_amount >= 0", name="ck_paid_non_negative"),
#         CheckConstraint("due_amount >= 0", name="ck_due_amount_non_negative"),
#         CheckConstraint(
#             "discount_amount <= total_amount + tax_amount",
#             name="ck_discount_valid"
#         ),
#         CheckConstraint(
#             "(status != 'CLOSED') OR (closed_at IS NOT NULL)",
#             name="ck_closed_requires_timestamp"
#         ),
#
#         # Indexes
#         Index("ix_folio_reservation", "is_deleted", "reservation_id", "id"),
#         Index("ix_folio_guest", "is_deleted", "guest_id", "id"),
#         Index("ix_folio_status", "is_deleted", "status", "id"),
#         Index("ix_folio_number", "is_deleted", "folio_number"),
#
#         # Unique active folio per reservation
#         Index(
#             "uq_folio_reservation_active",
#             "reservation_id",
#             unique=True,
#             postgresql_where=text("is_deleted = false")
#         ),
#     )
#
#     # =========================================================
#     # METHODS
#     # =========================================================
#     def __repr__(self):
#         return f"Folio(id={self.id}, folio_number='{self.folio_number}', status='{self.status}')"
#
#     def calculate_payable_amount(self) -> Decimal:
#         """total + tax - discount (safe)"""
#         return max(
#             self.total_amount + self.tax_amount - self.discount_amount,
#             Decimal("0.00")
#         )
#
#     def calculate_due_amount(self) -> Decimal:
#         """payable - paid (safe)"""
#         return max(
#             self.calculate_payable_amount() - self.paid_amount,
#             Decimal("0.00")
#         )
#
#     def update_amounts(self) -> None:
#         """sync payable & due"""
#         self.payable_amount = self.calculate_payable_amount()
#         self.due_amount = self.calculate_due_amount()
#
#     def is_paid_in_full(self) -> bool:
#         return self.due_amount == Decimal("0.00")
#
#     def can_be_closed(self) -> bool:
#         return self.status == FolioStatusEnum.OPEN and self.is_paid_in_full()
#
#     def close_folio(self) -> None:
#         """
#         Only updates status.
#         closed_at MUST be set from service:
#         folio.closed_at = func.now()
#         """
#         if not self.can_be_closed():
#             raise ValueError("Folio cannot be closed. Must be paid in full.")
#
#         self.status = FolioStatusEnum.CLOSED