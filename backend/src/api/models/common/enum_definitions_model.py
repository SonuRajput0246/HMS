from src.database.base import Base
from sqlalchemy import String, Text, Boolean, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.api.models.common.enum_options_model import EnumOption


class EnumDefinition(Base):
    __tablename__ = "enum_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)

    enum_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True
    )

    enum_label: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    ### RELATIONSHIPS
    options: Mapped[list["EnumOption"]] = relationship(
        "EnumOption",
        back_populates="enum_definition",
        cascade="all, delete-orphan",
        order_by="EnumOption.sort_order"
    )

    ### CONSTRAINTS & INDEXES
    __table_args__ = (
        Index("ix_enum_definitions_enum_key", "is_deleted", "enum_key"),
        Index("ix_enum_definitions_is_system", "is_deleted", "is_system", "id"),
    )

    def __repr__(self):
        return f"EnumDefinition(id={self.id}, enum_key='{self.enum_key}')"