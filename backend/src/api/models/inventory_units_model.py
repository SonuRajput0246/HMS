from datetime import datetime
from src.database.base import Base
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import mapped_column, Mapped


class InventoryUnits(Base):
    __tablename__ = 'inventory_units'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


    def __repr__(self):
        return f"Inventory Units(id={self.id}, name={self.code}, label={self.label})"