# from decimal import Decimal
# from enum import Enum
# from datetime import datetime
#
# from sqlalchemy import (
#     Enum as SqlEnum,
#     Text,
#     Numeric,
#     Integer,
#     ForeignKey,
#     DateTime,
#     Index,
#     CheckConstraint, String
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from typing import TYPE_CHECKING
#
# from src.database.base_model import BaseModel
#
#
# if TYPE_CHECKING:
#     from src.api.models.payment_model import Payment
#
#
# class RefundStatusEnum(str, Enum):
#     INITIATED = "INITIATED"
#     COMPLETED = "COMPLETED"
#     FAILED = "FAILED"
#
#
# class Refund(BaseModel):
#     __tablename__ = "refunds"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     payment_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("payments.id", ondelete="CASCADE"),
#         nullable=False
#     )
#
#     amount: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#     currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
#
#     base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
#
#     exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)
#
#     reason: Mapped[str | None] = mapped_column(
#         Text,
#         nullable=True
#     )
#
#     status: Mapped[RefundStatusEnum] = mapped_column(
#         SqlEnum(RefundStatusEnum),
#         nullable=False,
#         default=RefundStatusEnum.INITIATED
#     )
#
#     processed_at: Mapped[datetime | None] = mapped_column(
#         DateTime(timezone=True),
#         nullable=True
#     )
#
#     # -------------------------
#     # RELATIONSHIP
#     # -------------------------
#     payment: Mapped["Payment"] = relationship(
#         "Payment",
#         back_populates="refunds"
#     )
#
#     # -------------------------
#     # CONSTRAINTS & INDEXES
#     # -------------------------
#     __table_args__ = (
#         CheckConstraint("amount > 0", name="ck_refund_amount_positive"),
#
#         Index("ix_refund_payment", "is_deleted", "payment_id", "id"),
#         Index("ix_refund_status", "is_deleted", "status", "id"),
#         Index("ix_refund_processed_at", "is_deleted", "processed_at", "id"),
#     )
#
#     # =========================================================
#     # METHODS
#     # =========================================================
#     def __repr__(self):
#         return f"Refund(id={self.id}, amount={self.amount}, status='{self.status}')"
#
#     def mark_completed(self) -> None:
#         if self.status == RefundStatusEnum.COMPLETED:
#             raise ValueError("Refund is already completed")
#
#         self.status = RefundStatusEnum.COMPLETED
#         self.processed_at = datetime.utcnow()
#
#     def mark_failed(self) -> None:
#         if self.status == RefundStatusEnum.COMPLETED:
#             raise ValueError("Cannot mark completed refund as failed")
#
#         self.status = RefundStatusEnum.FAILED
#         self.processed_at = datetime.utcnow()
#
#     def is_initiated(self) -> bool:
#         return self.status == RefundStatusEnum.INITIATED
#
#     def is_completed(self) -> bool:
#         return self.status == RefundStatusEnum.COMPLETED
#
#     def is_failed(self) -> bool:
#         return self.status == RefundStatusEnum.FAILED
#
#     def is_processed(self) -> bool:
#         return self.is_completed() or self.is_failed()
#
#     def can_be_cancelled(self) -> bool:
#         return self.is_initiated()
#
#     def set_reason(self, reason: str | None) -> None:
#         self.reason = reason.strip() if reason else None
#
#     def get_display_status(self) -> str:
#         return {
#             RefundStatusEnum.INITIATED: "Initiated",
#             RefundStatusEnum.COMPLETED: "Completed",
#             RefundStatusEnum.FAILED: "Failed"
#         }.get(self.status, "Unknown")
#
#     def get_refund_info(self) -> dict:
#         return {
#             "id": self.id,
#             "payment_id": self.payment_id,
#             "amount": float(self.amount),
#             "reason": self.reason,
#             "status": self.status.value,
#             "display_status": self.get_display_status(),
#             "processed_at": self.processed_at.isoformat() if self.processed_at else None,
#             "is_processed": self.is_processed(),
#             "can_be_cancelled": self.can_be_cancelled()
#         }
#
#     def validate_amount(self, payment_amount: Decimal) -> None:
#         if self.amount <= Decimal("0.00"):
#             raise ValueError("Refund amount must be positive")
#
#         if self.amount > payment_amount:
#             raise ValueError("Refund amount cannot exceed original payment amount")
#
#     def can_be_processed(self) -> bool:
#         return self.is_initiated() and self.amount > Decimal("0.00")