from sqlalchemy import Index
from datetime import datetime
from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint

if TYPE_CHECKING:
    from src.api.models.role_model import Role
    from src.api.models.token_model import Token


class User(BaseModel, TenantScoped):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    last_password_update_at: Mapped[datetime | None] =  mapped_column(
        DateTime(timezone=True),
        default=None
    )
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deactivated_by: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        default=None
    )
    deactivation_reason: Mapped[str] = mapped_column(String(255), nullable=True)
    deactivated_at: Mapped[datetime | None] =  mapped_column(
        DateTime(timezone=True),
        default=None
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str] = mapped_column(String(32), nullable=True)


    ## Relationships
    role: Mapped["Role"] = relationship(back_populates="users")
    tokens: Mapped["Token"] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint("CHAR_LENGTH(TRIM(first_name)) > 0", name="ck_user_first_name"),
        CheckConstraint("CHAR_LENGTH(TRIM(last_name)) > 0", name="ck_user_last_name"),
        CheckConstraint(
        ## Structural check only: one character, '@', one character, '.', two
        ## characters. Real validation stays in the schema layer.
        ##
        ## This replaced INSTR(email,'@') > 1 AND INSTR(email,'.') >
        ## INSTR(email,'@'), which reads as "the FIRST dot must come after the
        ## @". INSTR returns the first match, so a dot anywhere in the local
        ## part -- first.last@gmail.com -- put it before the '@' and the insert
        ## was refused by the database. Registration then reported a generic
        ## internal error, because the schema's email field accepts those
        ## addresses and only the insert rejected them.
        ## Kept in step with revision a7f3c21d9b40.
        "email LIKE '_%@_%.__%'",
        name="ck_user_email_format",
    ),

        # 1. Pagination & Base Filter
        Index("ix_user_active_id", "is_deleted", "id"),

        # 2. Full-Text Search (Names)
        Index("ix_user_fts_search", "first_name", "last_name", "email", mysql_prefix="FULLTEXT"),

        # 3. Email Lookup / Duplicate Check / Prefix Search
        Index("ix_user_active_email", "tenant_id", "is_deleted", "email"),
    )

    def __repr__(self):
        return f"User(id={self.id}, email={self.email})"