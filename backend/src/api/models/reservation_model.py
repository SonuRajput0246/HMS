from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, Numeric, CheckConstraint, Boolean, text, UniqueConstraint
from src.database.base_model import BaseModel
from src.database.tenant_scoped import TenantScoped
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, DateTime, Index
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.api.models.room_model import Room
    from src.api.models.user_model import User
    from src.api.models.payment_model import Payment
    from src.api.models.reservation_primary_guest_model import ReservationPrimaryGuest
    from src.api.models.reservation_additional_guest_model import ReservationAdditionalGuest


class Reservation(BaseModel, TenantScoped):
    __tablename__ = 'reservations'

    id: Mapped[int] = mapped_column(primary_key=True)
    ## Unique per hotel, not per install -- see uq_reservations_tenant_number.
    ## Numbers are minted from reservation_sequences, which are themselves
    ## per-tenant, so two hotels legitimately generate the same
    ## "RES-202610-00001" and a global UNIQUE would refuse the second hotel's
    ## first booking of the month.
    reservation_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False
    )
    check_in_date: Mapped[datetime | None] =  mapped_column(
        DateTime(timezone=True),
        default=None
    )
    check_out_date: Mapped[datetime | None] =  mapped_column(
        DateTime(timezone=True),
        default=None
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    total_nights: Mapped[Decimal] = mapped_column(Integer, nullable=False, default=1)
    total_amount_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0")
    )
    total_amount_override_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    reservation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="created"
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    cancelled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    total_adults: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_children: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_infants: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


    ## Relationships
    room: Mapped["Room"] = relationship(back_populates="reservations")
    created_by_user: Mapped["User"] = relationship(foreign_keys=[created_by], lazy="joined")
    cancelled_by_user: Mapped["User | None"] = relationship(foreign_keys=[cancelled_by], lazy="joined")
    primary_guest_link: Mapped["ReservationPrimaryGuest"] = relationship(
        back_populates="reservation",
        uselist=False,
        cascade="all, delete-orphan"
    )
    additional_guest_link: Mapped[list["ReservationAdditionalGuest"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        ## `>=`, not `>`: a same-day booking (check_out == check_in) is a
        ## legitimate stay that is charged one full night. The old strict `>`
        ## made every such booking fail at flush with a raw
        ## ck_valid_date_range violation, surfacing as a 500 instead of a
        ## validation error. Overlap detection in reservation_service widens
        ## these zero-night windows to one day so a same-day room cannot be
        ## sold twice.
        CheckConstraint("check_out_date >= check_in_date", name="ck_valid_date_range"),

        ## Reservation numbers are unique within a hotel, and only within a
        ## hotel -- see the note on the column above.
        UniqueConstraint("tenant_id", "reservation_number", name="uq_reservations_tenant_number"),

        ## For "Get Available Rooms" (Reservation Service)
        Index(
            "ix_reservation_availability",
            "is_deleted",
            "room_id",
            "check_in_date",
            "check_out_date"
        ),

        ## For "Create Reservation" (Reservation Service)
        Index(
            "ix_reservation_conflict_check",
            "room_id",
            "is_deleted",
            "reservation_status",
            "check_in_date",
            "check_out_date"
        ),

        ## For "Get Reservation" (Reservation Service)
        Index(
            "ix_reservation_date_filter",
            "is_deleted",
            "check_in_date",
            "check_out_date",
            "id"
        ),
        Index(
            "ix_reservation_status_filter",
            "is_deleted",
            "reservation_status",
            "id"
        ),
    )

    def __repr__(self):
        return f"Reservation(id={self.id})"