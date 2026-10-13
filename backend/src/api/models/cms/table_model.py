from sqlalchemy import String, Boolean, Integer, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base_model import BaseModel
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.api.models.cms.table_zone_model import TableZone
    from src.api.models.cms.order_model import CMSOrder


class Table(BaseModel):
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    table_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=4, server_default="4")
    
    # Status: available, occupied, reserved, cleaning, maintenance
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", server_default="available")
    
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("table_zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Optional: floor plan coordinates
    position_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shape: Mapped[str | None] = mapped_column(String(20), nullable=True)  # square, round, rectangle
    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    is_combinable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")  # Can combine with adjacent

    # Relationships
    zone: Mapped["TableZone | None"] = relationship(
        "TableZone",
        back_populates="tables"
    )
    orders: Mapped[List["CMSOrder"]] = relationship(
        "CMSOrder",
        back_populates="table",
        foreign_keys="CMSOrder.table_id"
    )

    __table_args__ = (
        Index("ix_table_active_status", "is_deleted", "is_active", "status", "id"),
        Index("ix_table_zone_status", "is_deleted", "zone_id", "status", "id"),
        Index("ix_table_number", "is_deleted", "table_number"),
    )

    def __repr__(self):
        return f"Table(id={self.id}, table_number={self.table_number}, status={self.status})"

    def is_available(self) -> bool:
        return self.is_active and not self.is_deleted and self.status == "available"

    def can_be_occupied(self) -> bool:
        return self.status in ("available", "reserved")

    def occupy(self) -> None:
        if not self.can_be_occupied():
            raise ValueError(f"Table {self.table_number} cannot be occupied (status: {self.status})")
        self.status = "occupied"

    def free(self) -> None:
        self.status = "available"

    def reserve(self) -> None:
        if self.status != "available":
            raise ValueError(f"Only available tables can be reserved")
        self.status = "reserved"

    def set_cleaning(self) -> None:
        self.status = "cleaning"

    def set_maintenance(self) -> None:
        self.status = "maintenance"