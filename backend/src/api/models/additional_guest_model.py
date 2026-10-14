from typing import TYPE_CHECKING
from sqlalchemy import String, Integer
from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy.orm import Mapped, mapped_column, relationship


if TYPE_CHECKING:
    from src.api.models.reservation_additional_guest_model import ReservationAdditionalGuest

class AdditionalGuest(BaseModel, TenantScoped):
    __tablename__ = "additional_guests"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    id_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        default=None
    )
    id_number: Mapped[str] = mapped_column(String(50), nullable=True, default=None)

    ## Relationship
    reservation_links: Mapped[list["ReservationAdditionalGuest"]] = relationship(
        back_populates="additional_guest",
        cascade="save-update, merge"
    )


    def __repr__(self):
        return f"<AdditionalGuest (id={self.id}, full_name='{self.full_name}')>"