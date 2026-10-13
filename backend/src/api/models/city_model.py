from typing import TYPE_CHECKING
from src.database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Integer, ForeignKey, UniqueConstraint, text

if TYPE_CHECKING:
    from src.api.models.state_model import State

class City(Base):
    __tablename__ = 'cities'

    id: Mapped[int] = mapped_column(primary_key=True)
    state_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    ## Relationship
    state: Mapped["State"] = relationship(back_populates="cities")


    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_city_state_name"),
    )


    def __repr__(self):
        return f"Cities(id={self.id}, name={self.name})"

