from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy import ForeignKey, UniqueConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.models.role_model import Role
    from src.api.models.module_model import Module


class RoleModuleAccess(BaseModel, TenantScoped):
    __tablename__ = "role_module_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False
    )
    operation_key: Mapped[str] = mapped_column(String(50), nullable=False)  # Create, Edit, Delete, View, Payment, Split, Void
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    role: Mapped["Role"] = relationship(back_populates="module_access")
    module: Mapped["Module"] = relationship()

    __table_args__ = (
        UniqueConstraint("role_id", "module_id", "operation_key", name="uq_role_module_op"),
        Index("ix_role_module_access_role", "role_id", "is_active"),
        Index("ix_role_module_access_module", "module_id", "is_active"),
    )

    def __repr__(self):
        return f"RoleModuleAccess(role_id={self.role_id}, module_id={self.module_id}, op={self.operation_key})"