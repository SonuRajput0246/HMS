from sqlalchemy import String, Integer, Numeric, DateTime, Boolean, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base_model import BaseModel
from src.api.utils.datetime_helper import utcnow
from datetime import datetime
from typing import TYPE_CHECKING, List
from decimal import Decimal

if TYPE_CHECKING:
    from src.api.models.cms.order_model import CMSOrder


class Customer(BaseModel):
    __tablename__ = "customers"

    ## Loyalty tier thresholds on lifetime spend. Tuned for a cafe rather than
    ## a hotel: a regular guest might spend ~1,000 a month, so Silver starts at
    ## roughly one visit and Platinum needs sustained loyalty. Adjust here
    ## rather than scattering magic numbers through the code.
    SILVER_THRESHOLD = Decimal("1000")
    GOLD_THRESHOLD = Decimal("5000")
    PLATINUM_THRESHOLD = Decimal("15000")

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Loyalty
    loyalty_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00")
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Preferences
    preferred_table_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK to tables, but optional
    dietary_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    is_vip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    # Relationships
    orders: Mapped[List["CMSOrder"]] = relationship(
        "CMSOrder",
        back_populates="customer",
        foreign_keys="CMSOrder.customer_id"
    )

    __table_args__ = (
        Index("ix_customer_active_phone", "is_deleted", "is_active", "phone"),
        Index("ix_customer_code", "is_deleted", "customer_code"),
        Index("ix_customer_name", "is_deleted", "name"),
        Index("ix_customer_vip", "is_deleted", "is_vip", "is_active"),
    )

    def __repr__(self):
        return f"Customer(id={self.id}, customer_code={self.customer_code}, name={self.name})"

    def record_visit(self, amount: Decimal) -> None:
        """Call when an order is completed.

        Each counter is coerced first because SQLAlchemy applies column
        defaults at INSERT, not at __init__: on a freshly constructed (not yet
        flushed) instance these attributes read as None and a bare += would
        raise TypeError.
        """
        amount = Decimal(str(amount or 0))

        self.total_visits = (self.total_visits or 0) + 1
        self.total_spent = (self.total_spent or Decimal("0.00")) + amount
        self.last_visit_at = utcnow()
        # Simple loyalty: 1 point per 10 currency units spent
        self.loyalty_points = (self.loyalty_points or 0) + int(amount / 10)

    def redeem_points(self, points: int) -> bool:
        available = self.loyalty_points or 0
        if available >= points:
            self.loyalty_points = available - points
            return True
        return False

    def get_tier(self) -> str:
        """Loyalty tier derived from lifetime spend."""
        spent = self.total_spent or Decimal("0.00")
        if spent >= self.PLATINUM_THRESHOLD:
            return "PLATINUM"
        if spent >= self.GOLD_THRESHOLD:
            return "GOLD"
        if spent >= self.SILVER_THRESHOLD:
            return "SILVER"
        return "REGULAR"