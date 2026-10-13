from sqlalchemy import String, Integer, Text, Numeric, Boolean, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base_model import BaseModel
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.api.models.cms.recipe_category_model import RecipeCategory
    from src.api.models.cms.recipe_ingredient_model import RecipeIngredient


## NOTE: there is deliberately no StationEnum / SpiceLevelEnum here.
## Both live in the enum tables (enum_key 'recipe_station' and 'spice_level')
## so the values are admin-editable and consistent with every other dropdown in
## the app. Recipe.station is a plain string validated through EnumHelper.
## The migration creates `recipes.station` as VARCHAR(20) to match.


class Recipe(BaseModel):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipe_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ## Chef-facing method steps. Separate from `description`, which is the
    ## customer-facing blurb shown on the POS menu.
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Pricing
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Kitchen routing (KDS)
    ## Stored as a plain string, not a Python/SQL enum: the allowed values come
    ## from enum_definitions/enum_options under 'recipe_station', which is the
    ## app-wide single source of truth for dropdown values (see
    ## src/api/utils/enum_helper.py). An admin adding a station in the UI must
    ## not require a migration or a deploy, and the seeded keys stay lower-case
    ## so they match option_key directly.
    station: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="other",
        server_default="other"
    )
    prep_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cook_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Dietary / attributes
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_vegan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_spicy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    ## Free-text recipe steps. enum_key 'spice_level' holds the dropdown values.
    default_spice_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    # Relationships
    category: Mapped[Optional["RecipeCategory"]] = relationship(
        "RecipeCategory",
        back_populates="recipes"
    )
    ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("selling_price >= 0", name="ck_recipe_selling_price_nonneg"),
        CheckConstraint("cost_price >= 0", name="ck_recipe_cost_price_nonneg"),
        CheckConstraint("prep_time_minutes >= 0", name="ck_recipe_prep_time_nonneg"),
        CheckConstraint("cook_time_minutes >= 0", name="ck_recipe_cook_time_nonneg"),

        Index("ix_recipe_active_category", "is_deleted", "is_active", "category_id", "display_order", "id"),
        Index("ix_recipe_station", "is_deleted", "is_active", "station"),
        Index("ix_recipe_code", "is_deleted", "recipe_code"),
        Index("ix_recipe_name", "is_deleted", "name"),
        Index("ix_recipe_available", "is_deleted", "is_available", "is_active"),
    )

    def __repr__(self):
        return f"Recipe(id={self.id}, recipe_code={self.recipe_code}, name={self.name}, station={self.station})"

    def total_time(self) -> int:
        return (self.prep_time_minutes or 0) + (self.cook_time_minutes or 0)

    def calculate_cost_from_ingredients(self) -> Decimal:
        """Recompute cost_price from linked inventory items"""
        total = Decimal("0.00")
        for ing in self.ingredients:
            if ing.is_deleted:
                continue
            if ing.inventory_item is None:
                continue
            qty = Decimal(str(ing.quantity))
            unit_cost = Decimal(str(ing.inventory_item.unit_cost or 0))
            total += qty * unit_cost
        return total

    def update_cost_price(self) -> None:
        self.cost_price = self.calculate_cost_from_ingredients()

    def margin_percent(self) -> Decimal:
        if self.selling_price <= 0:
            return Decimal("0.00")
        margin = (self.selling_price - self.cost_price) / self.selling_price * 100
        return margin.quantize(Decimal("0.01"))

    def is_profitable(self) -> bool:
        return self.selling_price > self.cost_price

    def can_be_ordered(self) -> bool:
        return self.is_active and not self.is_deleted and self.is_available