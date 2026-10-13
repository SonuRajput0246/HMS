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
    ## CMS: per-unit purchase cost, used to compute recipe cost_price
    ## (Recipe.calculate_cost_from_ingredients reads this). NULL until an
    ## inventory manager fills it in, so existing rows stay valid.
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    ## CMS: sell price for items that can be ringed up directly without being a
    ## Recipe (bottled water, takeaway packets). NULL means "not directly
    ## sellable" and the POS forces staff to pick a Recipe instead. Recipes
    ## carry their own selling_price, so this is only read when
    ## cms_order_items.item_type == 'inventory'.
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
