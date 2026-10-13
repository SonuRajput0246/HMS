from sqlalchemy import String, Boolean
from src.database.base_model import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models.hms.room_type_amenity_model import RoomTypeAmenity
    from src.api.models.hms.room_model import Room


class RoomType(BaseModel):
    __tablename__ = 'room_types'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    max_adults: Mapped[int] = mapped_column(nullable=False)
    max_children: Mapped[int] = mapped_column(nullable=False)
    max_infants: Mapped[int] = mapped_column(default=1, nullable=False)
    base_price: Mapped[int] = mapped_column(nullable=False)
    extra_bed_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_bed_price: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    ## Relationships
    room_amenities: Mapped[list["RoomTypeAmenity"]] = relationship(
        back_populates="room_type",
        cascade="all, delete-orphan"
    )
    rooms: Mapped['Room'] = relationship(back_populates="room_type")


    def __repr__(self):
        return f"RoomType(id={self.id}, name={self.name})"