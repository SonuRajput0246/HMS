from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy import String, Float, Boolean, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship


if TYPE_CHECKING:
    from src.api.models.common.inventory_category_model import InventoryCategory

class Inventory(BaseModel):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_categories.id"),
        nullable=False,
        index=True
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    ## Purchase cost per unit, used to value stock on hand. NULL until an
    ## inventory manager fills it in, so existing rows stay valid and null is
    ## how the cost model says "unknown" rather than "free".
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    ## Default sell price for the item. NULL means no price has been set, which
    ## is distinct from a price of zero.
    selling_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ## Relationships
    category: Mapped["InventoryCategory"] = relationship(back_populates="inventory_items")

    __table_args__ = (
        Index("ix_active_inventory_name_id", "is_deleted", "name", "id"),
        Index("ix_active_inventory_id", "is_deleted", "id"),
    )

    def __repr__(self):
        return f"Inventory(id={self.id}, name={self.name})"
