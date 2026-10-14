from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, Numeric, Text, CheckConstraint, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped


if TYPE_CHECKING:
    from src.api.models.reservation_model import Reservation


### MODEL
class Payment(BaseModel, TenantScoped):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False
    )
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

    ### CONSTRAINTS & INDEXES
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),

        Index("ix_payment_reservation", "is_deleted", "reservation_id", "id"),
        Index("ix_payment_status", "is_deleted", "payment_status", "id"),
        Index("ix_payment_type", "is_deleted", "payment_type", "id"),
        Index("ix_payment_method", "is_deleted", "payment_method", "id"),
        Index("ix_payment_transaction_ref", "is_deleted", "transaction_ref"),
        Index("ix_payment_paid_at", "is_deleted", "paid_at", "id"),
    )

    def __repr__(self):
        return f"Payment(id={self.id}, type='{self.payment_type}', amount={self.amount}, status='{self.payment_status}')"