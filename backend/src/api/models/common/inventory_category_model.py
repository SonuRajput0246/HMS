from typing import List, TYPE_CHECKING
from sqlalchemy import String, Boolean, Index
from src.database.base_model import BaseModel
from sqlalchemy.orm import relationship, Mapped, mapped_column


if TYPE_CHECKING:
    from src.api.models.common.inventory_model import Inventory

class InventoryCategory(BaseModel):
    __tablename__ = "inventory_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


    ## Relationship
    inventory_items: Mapped[List["Inventory"]] = relationship(back_populates="category")

    __table_args__ = (
        Index("ix_active_category_name_id", "is_deleted", "name", "id"),
        Index("ix_active_category_id", "is_deleted", "id"),
    )

    def __repr__(self):
        return f"Inventory Category(id={self.id}, name={self.name})"
