from datetime import datetime
from src.database.base import Base
from sqlalchemy import Boolean, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column


class BaseModel(Base):
    """
    Abstract base class for all models.
    It will not create a table in the DB (because __abstract__ = True).
    """
    __abstract__ = True

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] =  mapped_column(DateTime(timezone=True), nullable=True)


    def to_dict(self):
        """
        Helper to quickly serialize model data for debugging or simple APIs.
        """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}