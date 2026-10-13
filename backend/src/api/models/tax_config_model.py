# from decimal import Decimal
#
# from sqlalchemy import (
#     String,
#     Numeric,
#     Boolean,
#     CheckConstraint,
#     Index
# )
# from sqlalchemy.orm import Mapped, mapped_column
#
# from src.database.base_model import BaseModel
#
#
# class TaxConfig(BaseModel):
#     __tablename__ = "tax_config"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     name: Mapped[str | None] = mapped_column(
#         String(100),
#         nullable=True
#     )
#
#     percentage: Mapped[Decimal] = mapped_column(
#         Numeric(5, 2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#
#     is_active: Mapped[bool] = mapped_column(
#         Boolean,
#         nullable=False,
#         default=True
#     )
#
#     # -------------------------
#     # CONSTRAINTS & INDEXES
#     # -------------------------
#     __table_args__ = (
#         CheckConstraint("percentage >= 0", name="ck_tax_percentage_non_negative"),
#         CheckConstraint("percentage <= 100", name="ck_tax_percentage_max_100"),
#
#         Index("ix_tax_config_active", "is_deleted", "is_active", "id"),
#         Index("ix_tax_config_name", "is_deleted", "name"),
#         Index("ix_tax_config_percentage", "is_deleted", "percentage", "id"),
#     )
#
#     # =========================================================
#     # METHODS
#     # =========================================================
#     def __repr__(self):
#         return f"TaxConfig(id={self.id}, name='{self.name}', percentage={self.percentage}%, active={self.is_active})"
#
#     def activate(self) -> None:
#         self.is_active = True
#
#     def deactivate(self) -> None:
#         self.is_active = False
#
#     def update_percentage(self, new_percentage: Decimal) -> None:
#         if new_percentage < 0:
#             raise ValueError("Tax percentage cannot be negative")
#
#         if new_percentage > Decimal("100.00"):
#             raise ValueError("Tax percentage cannot exceed 100")
#
#         self.percentage = new_percentage
#
#     def calculate_tax_amount(self, base_amount: Decimal) -> Decimal:
#         if base_amount < 0:
#             raise ValueError("Base amount cannot be negative")
#
#         return (base_amount * self.percentage) / Decimal("100.00")
#
#     def calculate_total_with_tax(self, base_amount: Decimal) -> Decimal:
#         tax_amount = self.calculate_tax_amount(base_amount)
#         return base_amount + tax_amount
#
#     def get_display_name(self) -> str:
#         if self.name:
#             return f"{self.name} ({self.percentage}%)"
#         return f"Tax {self.percentage}%"
#
#     def is_zero_tax(self) -> bool:
#         return self.percentage == Decimal("0.00")
#
#     def is_applicable(self) -> bool:
#         return self.is_active and not self.is_zero_tax()
#
#     def get_tax_info(self) -> dict:
#         return {
#             "id": self.id,
#             "name": self.name,
#             "percentage": float(self.percentage),
#             "is_active": self.is_active,
#             "display_name": self.get_display_name(),
#             "is_zero_tax": self.is_zero_tax(),
#             "is_applicable": self.is_applicable(),
#         }
#
#     @classmethod
#     def get_default_tax(cls) -> "TaxConfig":
#         return cls(
#             name="GST",
#             percentage=Decimal("18.00"),
#             is_active=True
#         )