from sqlalchemy import (
    String,
    Boolean,
    Integer,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from src.database.base import Base

if TYPE_CHECKING:
    from src.api.models.enum_definitions_model import EnumDefinition


class EnumOption(Base):
    __tablename__ = "enum_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    enum_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("enum_definitions.id", ondelete="CASCADE"),
        nullable=False
    )

    option_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    option_label: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
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
    enum_definition: Mapped["EnumDefinition"] = relationship(
        "EnumDefinition",
        back_populates="options"
    )

    ### CONSTRAINTS & INDEXES
    __table_args__ = (
        UniqueConstraint(
            "enum_id",
            "option_key",
            name="uq_enum_options_enum_id_option_key"
        ),
        Index("ix_enum_options_enum_id_active", "enum_id", "is_active", "sort_order"),
        Index("ix_enum_options_is_active", "is_deleted", "is_active", "enum_id"),
        Index("ix_enum_options_is_default", "is_deleted", "is_default", "enum_id"),
    )

    def __repr__(self):
        return f"EnumOption(id={self.id}, option_key='{self.option_key}', active={self.is_active})"