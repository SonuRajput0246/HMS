# from decimal import Decimal
# from enum import Enum
# from datetime import datetime
# from sqlalchemy import Enum as SqlEnum, String, Numeric, Boolean, CheckConstraint
# from src.database.base_model import BaseModel
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from sqlalchemy import Index
# from typing import TYPE_CHECKING
# from sqlalchemy import text  # ADD THIS
#
# if TYPE_CHECKING:
#     ## Only imported for type hints, prevents circular import loops
#     from src.api.models.folio_charges_model import FolioCharge
#
#
# class ServiceCategoryEnum(str, Enum):
#     FOOD = "FOOD"
#     LAUNDRY = "LAUNDRY"
#     SPA = "SPA"
#     TRANSPORT = "TRANSPORT"
#     OTHER = "OTHER"
#
#
# class Service(BaseModel):
#     __tablename__ = 'services'
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     name: Mapped[str] = mapped_column(
#         String(100),
#         nullable=False
#     )
#     category: Mapped[ServiceCategoryEnum] = mapped_column(
#         SqlEnum(ServiceCategoryEnum),
#         nullable=False
#     )
#     price: Mapped[Decimal] = mapped_column(
#         Numeric(precision=12, scale=2),
#         nullable=False,
#         default=Decimal("0.00")
#     )
#     is_active: Mapped[bool] = mapped_column(
#         Boolean,
#         nullable=False,
#         default=True
#     )
#
#     ## Relationships
#     folio_charges: Mapped[list["FolioCharge"]] = relationship(
#         "FolioCharge",
#         back_populates="service"
#     )
#
#     __table_args__ = (
#         CheckConstraint("price >= 0", name="ck_service_price_non_negative"),
#
#         ## For "Get Active Services" (Service Service)
#         Index(
#             "ix_service_active",
#             "is_deleted",
#             "is_active",
#             "id"
#         ),
#
#         ## For "Get Services by Category" (Service Service)
#         Index(
#             "ix_service_category",
#             "is_deleted",
#             "category",
#             "id"
#         ),
#
#         ## For "Service Name Search" (Service Service)
#         Index(
#             "ix_service_name",
#             "is_deleted",
#             "name"
#         ),
#
#         ## For "Service Price Filter" (Service Service)
#         Index(
#             "ix_service_price",
#             "is_deleted",
#             "price",
#             "id"
#         ),
#
#         Index(
#             "uq_service_name_active",
#             "name",
#             unique=True,
#             postgresql_where=text("is_deleted = false")
#         )
#     )
#
#     def __repr__(self):
#         return f"Service(id={self.id}, name='{self.name}', category='{self.category}', price={self.price})"
#
#     def activate(self) -> None:
#         """Activate the service"""
#         self.is_active = True
#
#     def deactivate(self) -> None:
#         """Deactivate the service"""
#         self.is_active = False
#
#     def update_price(self, new_price: Decimal) -> None:
#         """Update service price with validation"""
#         if new_price < 0:
#             raise ValueError("Price cannot be negative")
#         self.price = new_price
#
#     def is_food_service(self) -> bool:
#         """Check if this is a food service"""
#         return self.category == ServiceCategoryEnum.FOOD
#
#     def is_laundry_service(self) -> bool:
#         """Check if this is a laundry service"""
#         return self.category == ServiceCategoryEnum.LAUNDRY
#
#     def is_spa_service(self) -> bool:
#         """Check if this is a spa service"""
#         return self.category == ServiceCategoryEnum.SPA
#
#     def is_transport_service(self) -> bool:
#         """Check if this is a transport service"""
#         return self.category == ServiceCategoryEnum.TRANSPORT
#
#     def is_other_service(self) -> bool:
#         """Check if this is an other service"""
#         return self.category == ServiceCategoryEnum.OTHER
#
#     def can_be_charged(self) -> bool:
#         """Check if service can be charged (active and not deleted)"""
#         return self.is_active and not self.is_deleted
