from datetime import datetime
from src.database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, DateTime, String


class AccountDeletions(Base):
    __tablename__ = 'account_deletions'

    ## Mapped[int] tells the IDE this is an integer
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reason: Mapped[str | None] = mapped_column(String(255), default=None)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    account_deletion_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending"
    )
    account_deleted_by: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        default=None
    )
    account_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None
    )

    def __repr__(self):
        return f"AccountDeletions(id={self.id}, user_id={self.user_id})"












