from datetime import datetime
from src.database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index


class EmailOTP(Base):
    __tablename__ = 'email_otps'

    ## Mapped[int] tells the IDE this is an integer
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    otp_purpose: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    is_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


    ## Composite index for fast lookup of active OTP by user + purpose
    __table_args__ = (
        Index(
            "ix_user_purpose_active",
            "user_id",
            "is_used",
            "otp_purpose",
            "created_at"
        ),
    )

    def __repr__(self) -> str:
        return f"<EmailOTP(id={self.id}, user_id={self.user_id})>"