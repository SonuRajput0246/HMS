from src.database.base import Base
from sqlalchemy import String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column


class Currency(Base):
    __tablename__ = 'currencies'

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    def __repr__(self):
        return f"Currency(code={self.code})"
