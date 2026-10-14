from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy import String, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:
    from src.api.models.user_model import User
    from src.api.models.role_module_access_model import RoleModuleAccess


class Role(BaseModel, TenantScoped):
    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(primary_key=True)
    ## Uniqueness is (tenant_id, role_code) -- see uq_roles_tenant_code. The
    ## column is deliberately NOT unique=True and NOT separately indexed: a
    ## single-column UNIQUE would make role codes global, so the second hotel
    ## could not have an ADMIN role, and a bare (role_code) index would only
    ## duplicate the leading column of the constraint below.
    role_code: Mapped[str] = mapped_column(String(50), nullable=False)
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
        ## Role codes are unique per hotel, not per install. A bare
        ## UNIQUE(role_code) would let the first hotel to seed claim the code
        ## every other hotel needs.
        UniqueConstraint("tenant_id", "role_code", name="uq_roles_tenant_code"),

        Index("ix_active_role_name_id", "is_deleted", "role_name", "id"),
        Index("ix_active_role_id", "is_deleted", "id"),
        Index("ix_active_role_code", "tenant_id", "is_deleted", "role_code"),
    )

    def __repr__(self):
        return f"Role(id={self.id}, role_code={self.role_code}, role_name={self.role_name})"
