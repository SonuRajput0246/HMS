# from sqlalchemy import String, Boolean, ForeignKey, Index, CheckConstraint
# from src.database.base_model import BaseModel
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from datetime import date
# from enum import Enum
# from sqlalchemy import Enum as SqlEnum
#
#
# class PriceTypeEnum(str, Enum):
#     WEEKDAY = "weekday"
#     WEEKEND = "weekend"
#     HOLIDAY = "holiday"
#     SEASONAL = "seasonal"
#     CUSTOM = "custom"
#
#
# class AdjustmentTypeEnum(str, Enum):
#     PERCENTAGE = "percentage"
#     FIXED = "fixed"
#
# class RoomTypePricing(BaseModel):
#     __tablename__ = "room_type_pricing"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), nullable=False)
#     ## Pricing classification
#     ## values: WEEKDAY, WEEKEND, HOLIDAY, SEASONAL, CUSTOM
#     price_type: Mapped[PriceTypeEnum] = mapped_column(
#         SqlEnum(PriceTypeEnum),
#         nullable=False
#     )
#
#     # Date range (for seasonal / custom pricing)
#     start_date: Mapped[date] = mapped_column(nullable=True)
#     end_date: Mapped[date] = mapped_column(nullable=True)
#
#     # Days of week (for weekday/weekend logic)
#     # Example: "MON,TUE,WED" or "SAT,SUN"
#     days_of_week: Mapped[str] = mapped_column(String(50), nullable=True)
#
#     # Pricing
#     price: Mapped[int] = mapped_column(nullable=False)
#
#     min_occupancy: Mapped[int] = mapped_column(nullable=True)
#     max_occupancy: Mapped[int] = mapped_column(nullable=True)
#
#     adjustment_type: Mapped[AdjustmentTypeEnum] = mapped_column(
#         SqlEnum(AdjustmentTypeEnum),
#         nullable=True
#     )
#     # values: "percentage", "fixed"
#
#     adjustment_value: Mapped[int] = mapped_column(nullable=True)
#
#     # Priority (important for conflict resolution)
#     priority: Mapped[int] = mapped_column(default=0)
#
#     is_active: Mapped[bool] = mapped_column(Boolean, default=True)
#
#     ## Relationship
#     room_type = relationship("RoomType", backref="pricing_rules")
#
#     __table_args__ = (
#         Index("idx_room_type", "room_type_id"),
#         Index("idx_price_type", "price_type"),
#         Index("idx_date_range", "start_date", "end_date"),
#         Index("idx_active", "is_active"),
#
#         CheckConstraint("price >= 0", name="check_price_positive"),
#         CheckConstraint("min_occupancy >= 0", name="check_min_occ_positive"),
#         CheckConstraint("max_occupancy >= min_occupancy", name="check_occ_range"),
#     )
#
#
#     def __repr__(self):
#         return f"RoomTypePricing(id={self.id})"