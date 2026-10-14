from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, UniqueConstraint, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.database.tenant_scoped import TenantScoped

if TYPE_CHECKING:
    from src.api.models.reservation_model import Reservation
    from src.api.models.additional_guest_model import AdditionalGuest

class ReservationAdditionalGuest(Base, TenantScoped):
    __tablename__ = "reservation_additional_guests"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False
    )
    additional_guest_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("additional_guests.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ## Relationship
    reservation: Mapped["Reservation"] = relationship(
        back_populates="additional_guest_link",
        lazy="joined"
    )
    additional_guest: Mapped["AdditionalGuest"] = relationship(
        back_populates="reservation_links",
        lazy="joined"
    )


    __table_args__ = (
        UniqueConstraint("reservation_id", "additional_guest_id", name="uq_reservation_additional_guests"),
        Index("idx_reservation_id", "reservation_id"),
        Index("idx_additional_guest_id", "additional_guest_id"),
        Index("idx_reservation_additional", "reservation_id", "additional_guest_id"),
    )

    def __repr__(self):
        return f"<ReservationAdditionalGuest (id={self.id}')>"