from sqlalchemy import select
from datetime import datetime

from src.api.models.common.document_sequence_model import DocumentSequence
from src.api.models.common.prefixes_model import Prefixes


class DocumentSequenceService:
    """Builds prefixed, per-month document numbers.

    Follows the same shape as ReservationSequenceService (prefix lookup ->
    locked counter -> increment -> format) but is generic over `purpose`
    so orders, customers and recipes share one mechanism.

    The returned value is only unique for a successful caller: the caller must
    commit in the same transaction, otherwise a rolled-back create leaks a
    number (the sequence row is rolled back too, so the number is reused --
    which is safe because the order row never landed).
    """

    ## Width of the numeric tail. 5 digits = 99,999 documents per month.
    SEQUENCE_WIDTH = 5

    def __init__(self, db):
        self.db = db

    def generate(self, purpose: str) -> str:
        """Return the next document number for `purpose`.

        Raises ValueError if no active prefix exists for the purpose, which is a
        seeding/configuration problem rather than a user error.
        """
        now = datetime.now()
        year = now.year
        month = now.month

        prefix_stmt = select(Prefixes).where(
            Prefixes.purpose == purpose,
            Prefixes.is_active == True
        )
        prefix = self.db.execute(prefix_stmt).scalar_one_or_none()

        if not prefix:
            raise ValueError(f"No active prefix configured for purpose '{purpose}'.")

        stmt = select(DocumentSequence).where(
            DocumentSequence.purpose == purpose,
            DocumentSequence.period_year == year,
            DocumentSequence.period_month == month
        ).with_for_update()

        sequence_row = self.db.execute(stmt).scalar_one_or_none()

        if not sequence_row:
            sequence_row = DocumentSequence(
                purpose=purpose,
                period_year=year,
                period_month=month,
                last_sequence=0
            )
            self.db.add(sequence_row)
            self.db.flush()

        sequence_row.last_sequence += 1
        sequence = sequence_row.last_sequence

        ## e.g. ORD-202610-00042
        return f"{prefix.code}-{year}{month:02d}-{sequence:0{self.SEQUENCE_WIDTH}d}"