from sqlalchemy import String, Boolean
from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.api.models.room_type_amenity_model import RoomTypeAmenity


class RoomAmenity(BaseModel, TenantScoped):
    __tablename__ = 'room_amenities'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ## Relationships
    room_types: Mapped[list["RoomTypeAmenity"]] = relationship(
        back_populates="room_amenity",
        cascade="all, delete-orphan"
    )


    def __repr__(self):
        return f"RoomAmenities(id={self.id}, name={self.name})"

