from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, Text, CheckConstraint, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from src.database.base_model import BaseModel


if TYPE_CHECKING:
    from src.api.models.reservation_model import Reservation
    # from src.api.models.folio_model import Folio
    # from src.api.models.refund_model import Refund



### MODEL
class Payment(BaseModel):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False
    )
    # folio_id: Mapped[int | None] = mapped_column(
    #     Integer,
    #     ForeignKey("folios.id", ondelete="SET NULL"),
    #     nullable=True
    # )
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="INR"
    )
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    transaction_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    verified_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


    ### RELATIONSHIPS
    reservation: Mapped["Reservation"] = relationship(back_populates="payments")

    # folio: Mapped["Folio | None"] = relationship(
    #     "Folio",
    #     back_populates="payments"
    # )
    #
    # refunds: Mapped[list["Refund"]] = relationship(
    #     "Refund",
    #     back_populates="payment",
    #     cascade="all, delete-orphan"
    # )

    ### CONSTRAINTS & INDEXES
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),

        Index("ix_payment_reservation", "is_deleted", "reservation_id", "id"),
        # Index("ix_payment_folio", "is_deleted", "folio_id", "id"),
        Index("ix_payment_status", "is_deleted", "payment_status", "id"),
        Index("ix_payment_type", "is_deleted", "payment_type", "id"),
        Index("ix_payment_method", "is_deleted", "payment_method", "id"),
        Index("ix_payment_transaction_ref", "is_deleted", "transaction_ref"),
        Index("ix_payment_paid_at", "is_deleted", "paid_at", "id"),
    )

    ### METHODS
    def __repr__(self):
        return f"Payment(id={self.id}, type='{self.payment_type}', amount={self.amount}, status='{self.payment_status}')"

    def mark_success(self, transaction_ref: str | None = None) -> None:
        """Mark payment as successful"""
        self.payment_status = "success"
        self.paid_at = datetime.now(timezone.utc)

        if transaction_ref:
            self.transaction_ref = transaction_ref

    def mark_failed(self) -> None:
        """Mark payment as failed"""
        self.payment_status = "failed"
        self.paid_at = None


    ## STATUS CHECKS
    def is_successful(self) -> bool:
        return (self.payment_status or "").strip().lower() == "success"

    def is_pending(self) -> bool:
        return (self.payment_status or "").strip().lower() == "pending"

    def is_failed(self) -> bool:
        return (self.payment_status or "").strip().lower() == "failed"


    ## TYPE CHECKS
    def is_advance_payment(self) -> bool:
        return (self.payment_type or "").strip().lower() == "advance"

    def is_partial_payment(self) -> bool:
        return (self.payment_type or "").strip().lower() == "partial"

    def is_full_payment(self) -> bool:
        return (self.payment_type or "").strip().lower() == "full"


    ## BUSINESS LOGIC
    def can_be_refunded(self) -> bool:
        return (
            self.is_successful()
            and not self.is_refund_payment()
            and not self.is_refunded()
        )

    def set_gateway_response(self, response_data: dict) -> None:
        self.gateway_response = response_data

    def get_gateway_response(self) -> dict | None:
        return self.gateway_response