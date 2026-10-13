from datetime import datetime
from typing import TYPE_CHECKING
from src.database.base import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey, String, Boolean, Index, DateTime

if TYPE_CHECKING:
    from src.api.models.common.user_model import User


class Token(Base):
    __tablename__ = 'tokens'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    access_token: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ## Relations
    user: Mapped["User"] = relationship(back_populates="tokens")

    __table_args__ = (
        Index("ix_active_token", "user_id", "is_revoked"),
    )

    def __repr__(self):
        return f"Token(id={self.id})"