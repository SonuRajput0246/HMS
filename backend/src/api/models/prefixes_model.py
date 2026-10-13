from datetime import datetime
from src.database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, UniqueConstraint


class Prefixes(Base):
    __tablename__ = "prefixes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    ## Unique because document number generators resolve a prefix by purpose
    ## with scalar_one_or_none(), which raises MultipleResultsFound on a
    ## duplicate. The constraint is declared exactly once, in __table_args__:
    ## also passing `unique=True` here makes SQLAlchemy emit a SECOND constraint
    ## on the same column, and autogenerate then keeps trying to create both.
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("purpose", name="uq_prefixes_purpose"),
    )

    def __repr__(self):
        return f"<Prefix(id={self.id}, code='{self.code}', purpose='{self.purpose}')>"