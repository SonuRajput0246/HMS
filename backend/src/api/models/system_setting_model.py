from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))

    def __repr__(self):
        return f"SystemSetting(Key={self.key}, Value={self.value})"