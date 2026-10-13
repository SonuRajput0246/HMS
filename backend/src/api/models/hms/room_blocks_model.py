from datetime import datetime
from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, DateTime, String, Index

if TYPE_CHECKING:
    from src.api.models.hms.room_model import Room


class RoomBlocks(BaseModel):
    __tablename__ = 'room_blocks'

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False
    )
    start_date: Mapped[datetime | None] =  mapped_column(
        DateTime(timezone=True),
        default=None
    )
    end_date: Mapped[datetime | None] =  mapped_column(
        DateTime(timezone=True),
        default=None
    )
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ## Relationships
    room: Mapped["Room"] = relationship(backref="blocks")


    __table_args__ = (
        ## For "Get Available Rooms" && "Create Reservation" (Reservation Service)
        Index(
            "ix_room_blocks_conflict_check",
            "room_id",
            "is_deleted",
            "start_date",
            "end_date"
        ),

    )


    def __repr__(self):
        return f"RoomBlocks(id={self.id})"