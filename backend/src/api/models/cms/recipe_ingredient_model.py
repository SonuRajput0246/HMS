from sqlalchemy import String, Numeric, Boolean, ForeignKey, Index, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base_model import BaseModel
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.api.models.cms.recipe_model import Recipe
    from src.api.models.common.inventory_model import Inventory


class RecipeIngredient(BaseModel):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventory.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Quantity of inventory item needed per 1 unit of recipe
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("1.000"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_prepped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    # Relationships
    recipe: Mapped["Recipe"] = relationship(
        "Recipe",
        back_populates="ingredients"
    )
    inventory_item: Mapped["Inventory"] = relationship(
        "Inventory",
        foreign_keys=[inventory_id]
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_recipe_ing_qty_positive"),
        UniqueConstraint("recipe_id", "inventory_id", name="uq_recipe_inventory_ingredient"),
        Index("ix_recipe_ing_recipe", "is_deleted", "recipe_id", "id"),
        Index("ix_recipe_ing_inventory", "is_deleted", "inventory_id"),
    )

    def __repr__(self):
        return f"RecipeIngredient(recipe_id={self.recipe_id}, inventory_id={self.inventory_id}, qty={self.quantity}{self.unit})"

    def total_cost(self) -> Decimal:
        if self.inventory_item is None:
            return Decimal("0.00")
        return Decimal(str(self.quantity)) * Decimal(str(self.inventory_item.unit_cost or 0))

    def is_stock_available(self) -> bool:
        if self.inventory_item is None:
            return False
        return Decimal(str(self.inventory_item.quantity)) >= Decimal(str(self.quantity))