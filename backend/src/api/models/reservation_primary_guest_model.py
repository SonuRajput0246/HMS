from datetime import datetime
from typing import TYPE_CHECKING
from src.database.base import Base
from src.database.tenant_scoped import TenantScoped
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, UniqueConstraint, Index, DateTime

if TYPE_CHECKING:
    from src.api.models.reservation_model import Reservation
    from src.api.models.guest_model import Guest

class ReservationPrimaryGuest(Base, TenantScoped):
    __tablename__ = "reservation_primary_guests"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False
    )
    primary_guest_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("guests.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ## Relationship
    reservation: Mapped["Reservation"] = relationship(
        back_populates="primary_guest_link",
        lazy="joined"
    )
    guest: Mapped["Guest"] = relationship(
        back_populates="reservation_links",
        lazy="joined"
    )


    __table_args__ = (
        UniqueConstraint("reservation_id", name="uq_reservation_primary_guest"),
        Index("idx_reservation_id", "reservation_id"),
        Index("idx_primary_guest_id", "primary_guest_id"),
        Index("idx_reservation_guest", "reservation_id", "primary_guest_id"),
    )

    def __repr__(self):
        return f"<ReservationPrimaryGuest (id={self.id}')>"