from datetime import date
from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Date, Index, ForeignKey


if TYPE_CHECKING:
    from src.api.models.city_model import City
    from src.api.models.state_model import State
    from src.api.models.country_model import Country
    from src.api.models.reservation_primary_guest_model import ReservationPrimaryGuest

class Guest(BaseModel):
    __tablename__ = "guests"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(String(30), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), nullable=True)
    state_id: Mapped[int | None] = mapped_column(ForeignKey("states.id"), nullable=True)
    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"), nullable=True)
    nationality_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"), nullable=True)
    id_type: Mapped[str] = mapped_column(String(30), nullable=True, default=None)
    id_number: Mapped[str] = mapped_column(String(50), nullable=True, default=None)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    vip_status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blacklist_status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ## Relationships
    city: Mapped["City"] = relationship(backref="guests")
    state: Mapped["State"] = relationship(backref="guests")
    country: Mapped["Country"] = relationship(foreign_keys=[country_id], backref="residents")
    nationality: Mapped["Country"] = relationship(foreign_keys=[nationality_id], backref="nationals")
    reservation_links: Mapped[list["ReservationPrimaryGuest"]] = relationship(
        back_populates="guest",
        cascade="save-update, merge"
    )

    __table_args__ = (

        Index("ix_guest_email_active", "is_deleted", "email", "id"),

        Index("ix_guest_email_id_active", "is_deleted", "id"),

    )


    def __repr__(self):
        return f"<Guest (id={self.id}, first_name='{self.first_name})>"