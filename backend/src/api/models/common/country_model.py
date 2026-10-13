from typing import TYPE_CHECKING
from src.database.base import Base
from sqlalchemy import String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.models.common.state_model import State

class Country(Base):
    __tablename__ = 'countries'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    nationality: Mapped[str] = mapped_column(String(150), nullable=True)
    iso2_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    iso3_code: Mapped[str] = mapped_column(String(3), nullable=True)
    phone_code: Mapped[str] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))


    ## Relationship
    states: Mapped[list["State"]] = relationship(back_populates="country")


    def __repr__(self):
        return f"Countries(id={self.id}, name={self.name})"

