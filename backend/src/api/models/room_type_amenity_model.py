from datetime import datetime
from src.database.base_model import BaseModel
from sqlalchemy import Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models.room_type_model import RoomType
    from src.api.models.room_amenity_model import RoomAmenity


class RoomTypeAmenity(BaseModel):
    __tablename__ = 'room_type_amenities'

    id: Mapped[int] = mapped_column(primary_key=True)
    room_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("room_types.id", ondelete="CASCADE"),
        nullable=False
    )
    room_amenity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("room_amenities.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


    ## Relationships
    room_type: Mapped["RoomType"] = relationship(back_populates="room_amenities")
    room_amenity: Mapped["RoomAmenity"] = relationship(back_populates="room_types")


    def __repr__(self):
        return (
            f"<RoomTypeAmenity room_type_id={self.room_type_id} "
            f"room_amenity_id={self.room_amenity_id}>"
        )