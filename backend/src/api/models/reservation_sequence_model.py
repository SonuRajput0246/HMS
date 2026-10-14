from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy import Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models.prefixes_model import Prefixes


class ReservationSequence(BaseModel, TenantScoped):
    __tablename__ = "reservation_sequences"

    id: Mapped[int] = mapped_column(primary_key=True)

    prefix_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("prefixes.id", ondelete="CASCADE"),
        nullable=False
    )

    reservation_year: Mapped[int] = mapped_column(nullable=False)
    reservation_month: Mapped[int] = mapped_column(nullable=False)

    last_sequence: Mapped[int] = mapped_column(nullable=False, default=0)

    ## Relationship
    prefix: Mapped["Prefixes"] = relationship(lazy="joined")

    __table_args__ = (
        ## Unique per hotel + prefix + month. prefix_id already implies the
        ## tenant, so this is not needed for correctness -- it keeps the tenant
        ## boundary visible in the schema instead of inferable only through a
        ## join to prefixes.
        UniqueConstraint(
            "tenant_id", "prefix_id", "reservation_year", "reservation_month",
            name="uq_reservation_sequence_scope",
        ),

        ## Fast lookup
        Index(
            "ix_reservation_sequence_lookup",
            "tenant_id", "prefix_id", "reservation_year", "reservation_month",
        ),
    )

    def __repr__(self):
        return f"<reservationSequence(id={self.id}, prefix_id={self.prefix_id}, seq={self.last_sequence})>"