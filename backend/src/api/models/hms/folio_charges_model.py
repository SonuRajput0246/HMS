# from decimal import Decimal
# from enum import Enum
# from datetime import datetime
#
# from sqlalchemy import (
#     Enum as SqlEnum,
#     String,
#     Numeric,
#     CheckConstraint,
#     Integer,
#     ForeignKey,
#     DateTime,
#     Index
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from sqlalchemy.sql import func
# from typing import TYPE_CHECKING
#
# from src.database.base_model import BaseModel
#
# if TYPE_CHECKING:
#     # Only for type hints (avoids circular imports)
#     from src.api.models.hms.folio_model import Folio
#     from src.api.models.hms.services_model import Service
#
#
# # =========================================================
# # ENUM
# # =========================================================
# class ChargeTypeEnum(str, Enum):
#     ROOM = "room"
#     SERVICE = "service"
#     FOOD = "food"
#     LAUNDRY = "laundry"
#     SPA = "spa"
#     MINIBAR = "minibar"
#     TAX = "tax"
#     DISCOUNT = "discount"
#     OTHER = "other"
#
#
# # =========================================================
# # MODEL
# # =========================================================
# class FolioCharge(BaseModel):
#     __tablename__ = "folio_charges"
#
#     # -------------------------
#     # PRIMARY FIELDS
#     # -------------------------
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     folio_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("folios.id", ondelete="CASCADE"),
#         nullable=False
#     )
#
#     charge_type: Mapped[ChargeTypeEnum] = mapped_column(
#         SqlEnum(ChargeTypeEnum),
#         nullable=False
#     )
#
#     service_id: Mapped[int | None] = mapped_column(
#         Integer,
#         ForeignKey("services.id", ondelete="SET NULL"),
#         nullable=True
#     )
#
#     description: Mapped[str | None] = mapped_column(
#         String(255),
#         nullable=True
#     )
#
#     # -------------------------
#     # PRICING
#     # -------------------------
#     quantity: Mapped[Decimal] = mapped_column(
#         Numeric(10, 2),
#         nullable=False,
#         default=Decimal("1.00")
#     )
#
#     unit_price: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     total_price: Mapped[Decimal] = mapped_column(
#         Numeric(12, 2),
#         nullable=False
#     )
#
#     # -------------------------
#     # METADATA
#     # -------------------------
#     charge_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
#
#     reference_id: Mapped[int | None] = mapped_column(
#         Integer,
#         nullable=True
#     )
#
#     # -------------------------
#     # RELATIONSHIP
#     # -------------------------
#     folio: Mapped["Folio"] = relationship(
#         "Folio",
#         back_populates="charges"
#     )
#     service: Mapped["Service | None"] = relationship(
#         "Service",
#         back_populates="folio_charges"
#     )
#
#     # -------------------------
#     # CONSTRAINTS & INDEXES
#     # -------------------------
#     __table_args__ = (
#         CheckConstraint("quantity > 0", name="ck_quantity_positive"),
#         CheckConstraint("unit_price >= 0", name="ck_unit_price_non_negative"),
#         CheckConstraint("total_price >= 0", name="ck_total_price_non_negative"),
#
#         Index("ix_folio_charge_folio", "is_deleted", "folio_id", "id"),
#         Index("ix_folio_charge_type", "is_deleted", "folio_id", "charge_type", "id"),
#         Index("ix_folio_charge_date", "is_deleted", "folio_id", "charge_date", "id"),
#         Index("ix_folio_charge_service", "is_deleted", "service_id", "id"),
#     )
#
#     # =========================================================
#     # METHODS
#     # =========================================================
#     def __repr__(self):
#         return f"FolioCharge(id={self.id}, type='{self.charge_type}', amount={self.total_price})"
#
#     def calculate_total_price(self) -> Decimal:
#         """quantity * unit_price (safe)"""
#         return (self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
#
#     def update_total_price(self) -> None:
#         """sync total_price"""
#         self.total_price = self.calculate_total_price()
#
#     def is_discount_charge(self) -> bool:
#         return self.charge_type == ChargeTypeEnum.DISCOUNT
#
#     def is_tax_charge(self) -> bool:
#         return self.charge_type == ChargeTypeEnum.TAX
#
#     def is_room_charge(self) -> bool:
#         return self.charge_type == ChargeTypeEnum.ROOM
#
#     def apply_quantity_and_price(self, quantity: Decimal, unit_price: Decimal) -> None:
#         """set values safely and recalc"""
#         if quantity <= 0:
#             raise ValueError("Quantity must be greater than zero")
#
#         if unit_price < 0:
#             raise ValueError("Unit price cannot be negative")
#
#         self.quantity = quantity
#         self.unit_price = unit_price
#         self.update_total_price()