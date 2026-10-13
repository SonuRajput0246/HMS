from sqlalchemy import Index
from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy import String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.models.hms.room_type_model import RoomType
    from src.api.models.hms.reservation_model import Reservation


class Room(BaseModel):
    __tablename__ = 'rooms'

    id: Mapped[int] = mapped_column(primary_key=True)
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    room_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("room_types.id", ondelete="RESTRICT"),
        nullable=False
    )
    floor_number: Mapped[int] = mapped_column(nullable=False)
    room_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="available"
    )
    view: Mapped[str] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ## Relationships
    room_type: Mapped["RoomType"] = relationship(back_populates="rooms")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="room")


    __table_args__ = (
        ## Filtered List
        # 1. For Case: (Not deleted) + (Sort ID)
        Index("ix_room_active_id", "is_deleted", "id"),

        # 2. For Case: (Not deleted) + (Room Type) + (Sort ID)
        Index("ix_room_active_type_id", "is_deleted", "room_type_id", "id"),

        # 3. For Case: (Not deleted) + (Room Number/Name) + (Sort ID)
        Index("ix_room_active_number_id", "is_deleted", "room_number", "id"),

        # 4. For Case: (Not deleted) + (Room Type) + (Room Number/Name) + (Sort ID)
        Index("ix_room_active_type_number_id", "is_deleted", "room_type_id", "room_number", "id"),

        ## For "Get Available Rooms" (Reservation Service)
        Index(
            "ix_room_availability_search",
            "is_deleted",
            "is_active",
            "room_status",
            "room_type_id",
            "id"
        ),

        ## For "Create Reservation" (Reservation Service)
        Index("ix_room_validation", "id", "is_deleted", "is_active")

    )


    def __repr__(self):
        return f"<Room(id={self.id}, number='{self.room_number}', room_status='{self.room_status}')>"