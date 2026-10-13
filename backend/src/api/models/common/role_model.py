from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy import String, Boolean, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:
    from src.api.models.common.user_model import User
    from src.api.models.common.role_module_access_model import RoleModuleAccess


class Role(BaseModel):
    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(primary_key=True)
    role_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


    ## Relationship: Role -> RoleModuleAccess (one-to-many)
    module_access: Mapped[list["RoleModuleAccess"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan"
    )

    ## Relationship: Role -> User (one-to-many)
    users: Mapped[list["User"]] = relationship(
        back_populates="role"
    )

    __table_args__ = (
        Index("ix_active_role_name_id", "is_deleted", "role_name", "id"),
        Index("ix_active_role_id", "is_deleted", "id"),
        Index("ix_active_role_code", "is_deleted", "role_code"),  # Add this
    )

    def __repr__(self):
        return f"Role(id={self.id}, role_code={self.role_code}, role_name={self.role_name})"
