from sqlalchemy import select
from datetime import datetime

from src.api.models.reservation_sequence_model import ReservationSequence
from src.api.models.prefixes_model import Prefixes


class ReservationSequenceService:

    def __init__(self, db):
        self.db = db

    def generate(self) -> str:
        now = datetime.now()
        year = now.year
        month = now.month

        # 🔥 Fetch prefix from DB
        prefix_stmt = select(Prefixes).where(
            Prefixes.purpose == 'reservation',
            Prefixes.is_active == True
        )
        prefix = self.db.execute(prefix_stmt).scalar_one_or_none()

        if not prefix:
            raise ValueError(f"Invalid or inactive prefix.")

        # 🔥 Get sequence row with lock
        stmt = select(ReservationSequence).where(
            ReservationSequence.prefix_id == prefix.id,
            ReservationSequence.reservation_year == year,
            ReservationSequence.reservation_month == month
        ).with_for_update()

        sequence_row = self.db.execute(stmt).scalar_one_or_none()

        # 🔥 Create if not exists
        if not sequence_row:
            sequence_row = ReservationSequence(
                prefix_id=prefix.id,
                reservation_year=year,
                reservation_month=month,
                last_sequence=0
            )
            self.db.add(sequence_row)
            self.db.flush()

        # 🔥 Increment sequence
        sequence_row.last_sequence += 1
        sequence = sequence_row.last_sequence

        # 🔥 Generate reservation number
        return f"{prefix.code}-{year}{month:02d}-{sequence:05d}"