from sqlalchemy import Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base_model import BaseModel


class DocumentSequence(BaseModel):
    """Generic monotonic counter used to build human-readable document numbers.

    One table serves every numbered document (order, customer, recipe, table)
    instead of a bespoke sequence table per document type. The row is scoped by
    (purpose, period_year, period_month) so numbering restarts each month while
    the number stays sortable and unique.

    The service layer takes a row lock (SELECT ... FOR UPDATE) before
    incrementing, so two cashiers hitting "create order" at the same moment
    cannot read the same last_sequence and collide on the unique index.
    """
    __tablename__ = "document_sequences"

    id: Mapped[int] = mapped_column(primary_key=True)

    ## Which document this counts: 'order', 'customer', 'recipe', 'table'
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)

    ## Reset window. Both are kept so a future yearly scope needs no migration.
    period_year: Mapped[int] = mapped_column(nullable=False)
    period_month: Mapped[int] = mapped_column(nullable=False)

    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint(
            "purpose", "period_year", "period_month",
            name="uq_document_sequence_scope"
        ),
        Index(
            "ix_document_sequence_lookup",
            "purpose", "period_year", "period_month"
        ),
    )

    def __repr__(self):
        return (
            f"<DocumentSequence(purpose={self.purpose}, "
            f"period={self.period_year}-{self.period_month:02d}, "
            f"seq={self.last_sequence})>"
        )