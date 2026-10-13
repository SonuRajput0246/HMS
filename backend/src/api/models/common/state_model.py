from typing import TYPE_CHECKING
from src.database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Integer, ForeignKey, UniqueConstraint, text

if TYPE_CHECKING:
    from src.api.models.common.country_model import Country
    from src.api.models.common.city_model import City


class State(Base):
    __tablename__ = 'states'

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("countries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    state_code: Mapped[str] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    ## Relationship
    country: Mapped["Country"] = relationship(back_populates="states")
    cities: Mapped[list["City"]] = relationship(back_populates="state")

    __table_args__ = (
        UniqueConstraint("country_id", "name", name="uq_state_country_name"),
    )


    def __repr__(self):
        return f"States(id={self.id}, name={self.name})"

