import logging

from src.api.services.payment_service import PaymentService
from src.api.services.reservation_sequence_service import ReservationSequenceService
from src.api.services.guest_service import GuestService
from sqlalchemy import exists, and_, not_, func, literal_column
from src.api.models import Room, RoomBlocks, Reservation, ReservationPrimaryGuest, ReservationAdditionalGuest, Guest
from src.api.utils.enum_helper import EnumHelper, EnumUnavailableError
from src.api.utils.responses import service_response
from sqlalchemy.orm import joinedload, selectinload
from decimal import Decimal
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


## `enum_definitions.enum_key` values this service reads.
ROOM_STATUS_ENUM_KEY = "room_status"
RESERVATION_STATUS_ENUM_KEY = "reservation_status"

## ---------------------------------------------------------------------------
## RESERVATION LIFECYCLE TRANSITIONS
##
## These are deliberately NOT read from `enum_definitions`, and are not an
## allow-list. `cancelled` is a terminal state and `reserved` is the target of
## "a payment was recorded" -- neither is the *default* state, so
## `EnumOption.is_default` cannot express them. Only the two places that need a
## starting state (a new booking, an available room) come from the table.
##
## Modelling these properly needs a transition table keyed on an event
## (cancel / check_in / check_out / record_payment), which the schema does not
## have. Until it does, they stay here where they are at least greppable.
## ---------------------------------------------------------------------------
STATUS_CANCELLED = "cancelled"
STATUS_RESERVED = "reserved"

## A completed stay cannot be "un-stayed", so cancelling one would silently
## rewrite the record of what the guest actually consumed.
CANCELLABLE_STATUSES = ("created", STATUS_RESERVED, "checked_in")

## Longest reason accepted, matching the column width so the DB cannot reject a
## request the service already approved.
MAX_CANCELLATION_REASON = 255

## Age bands shared by every guest-count calculation in this file. They were
## duplicated three times with the boundaries spelled out inline; one place now
## owns them so the write path and the read path cannot disagree about whether
## an 11-year-old is a child or an adult.
INFANT_MAX_AGE = 3
ADULT_MIN_AGE = 12


class ReservationService:

    def __init__(self, db):
        self.db = db
        self.guest_service = GuestService(db=db)
        self.payment_service = PaymentService(db=db)
        self.enums = EnumHelper(db)


    # ===============================================================
    #  Stay window / pricing
    #
    #  A same-day booking (check_out == check_in, nights == 0) is legitimate
    #  and is charged one full night. It stores an empty half-open interval
    #  [check_in, check_out), so every plain `check_in < check_out AND
    #  check_out > check_in` overlap test silently treats it as occupying
    #  zero days -- which would let the same room be sold twice for that day.
    #  The helpers below expand a zero-night window to [check_in, check_in+1)
    #  on both sides of the comparison, and are used by every availability and
    #  conflict check in this service so the three call sites cannot drift.
    # ===============================================================
    @staticmethod
    def _stay_window(check_in, check_out):
        """Half-open day window, with a same-day booking widened to one day."""
        if check_out > check_in:
            return check_in, check_out
        return check_in, check_in + timedelta(days=1)


    @staticmethod
    def _live_reservation_filters(model=Reservation):
        """Filters defining a reservation that actually holds the room.

        A cancelled booking must not make a room look unavailable -- cancelling
        releases it back to inventory, and that is the whole point of cancelling.
        `get_available_rooms` used to filter only `is_deleted`, so the room picker
        hid rooms that `create_reservation` would have accepted, and the guest
        could never re-book the room they had just cancelled. Both sides now
        share this one definition so they cannot drift apart again.
        """
        return [
            model.is_deleted == False,
            model.reservation_status != STATUS_CANCELLED,
        ]


    @staticmethod
    def _reservation_overlap(check_in, check_out, model=Reservation):
        """Date predicates for 'does a stored stay clash with this window?'.

        `model` is passed so `get_available_rooms` can reuse the exact same
        logic in a correlated EXISTS rather than duplicating it.
        """
        start, end = ReservationService._stay_window(check_in, check_out)

        ## The stored row's end also has to be widened, otherwise a second
        ## same-day booking for the same room sees `check_out > check_in` as
        ## false and both are accepted.
        stored_end = func.greatest(
            model.check_out_date,
            func.date_add(model.check_in_date, literal_column("INTERVAL 1 DAY"))
        )
        return [model.check_in_date < end, stored_end > start]


    @staticmethod
    def _block_overlap(check_in, check_out, model=RoomBlocks):
        """Date predicates for room blocks, widened the same way."""
        start, end = ReservationService._stay_window(check_in, check_out)
        return [model.start_date < end, model.end_date > start]


    @staticmethod
    def _classify_age(age):
        """'infant' | 'child' | 'adult' for one age.

        The primary guest is always one adult. An unparseable or missing age
        falls back to adult: over-counting capacity is the safe direction for an
        occupancy limit, whereas defaulting to infant would let an unvalidated
        payload book a room that cannot hold the people in it.
        """
        if age is None:
            return "adult"
        try:
            age_int = int(age)
        except (ValueError, TypeError):
            return "adult"

        if age_int <= INFANT_MAX_AGE:
            return "infant"
        if age_int < ADULT_MIN_AGE:
            return "child"
        return "adult"


    @classmethod
    def _count_guests(cls, additional_guests, primary_adults=1):
        """(adults, children, infants) for a primary guest plus any additional.

        The primary guest is `primary_adults`, normally 1.
        """
        adults = primary_adults
        children = 0
        infants = 0

        for guest in additional_guests or []:
            band = cls._classify_age(guest.get("age"))
            if band == "infant":
                infants += 1
            elif band == "child":
                children += 1
            else:
                adults += 1

        return adults, children, infants


    @staticmethod
    def _parse_stay_dates(data: dict):
        """(check_in, check_out) as dates.

        Raises ValueError when either is missing or malformed. `strptime`
        already raised ValueError on a malformed date (the route turned that into
        a 500); the point of this helper is to make the missing-key case raise
        the same way instead of KeyError, so one `except` covers both.

        NOTE: this deliberately does NOT return a `service_response` tuple on
        failure. An earlier version did, and callers detected it with
        `isinstance(result, tuple)` -- but a successful parse returns a tuple
        too, so every valid booking was treated as a parse failure and the date
        pair was handed back to the caller as if it were a response. Callers
        must now wrap the call in try/except ValueError.
        """
        raw_in = data.get("check_in_date")
        raw_out = data.get("check_out_date")

        if not raw_in or not raw_out:
            raise ValueError("check_in_date and check_out_date are required")

        try:
            check_in = datetime.strptime(str(raw_in), "%Y-%m-%d").date()
            check_out = datetime.strptime(str(raw_out), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise ValueError(
                "check_in_date and check_out_date must be in YYYY-MM-DD format"
            ) from None

        return check_in, check_out


    @staticmethod
    def _actor_name(user):
        """'First Last' for an actor, or None when the row has no actor.

        `created_by` is nullable (seeded/system rows have no acting user), so
        this cannot assume a relationship is populated. `get_all_reservations`
        raised AttributeError on any such row.
        """
        if user is None:
            return None
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or None


    @staticmethod
    def _calculate_amount(nights, base_price):
        """`nights * rate`, except a same-day booking still bills one night.

        `Decimal(str(...))` rather than `Decimal(base_price)`: base_price comes
        off a Numeric column and can arrive as a float, which would import
        binary floating-point error into a money column.
        """
        return Decimal(str(base_price)) * max(nights, 1)



    def get_all_reservations(self, data: dict):
        from_date = data.get("from_date")
        to_date = data.get("to_date")
        room_number = data.get("search_room_number_value")
        reservation_status = data.get("reservation_status")
        page_size = data["page_size"]
        page_number = data["page_number"]

        query = (
            self.db.query(Reservation)
            .join(Room, Room.id == Reservation.room_id)
            .options(joinedload(Reservation.room))
            .filter(
                Reservation.is_deleted == False,
                Room.is_deleted == False
            )
        )

        ## Date range filter. Both bounds must be present -- a half-open range
        ## has no single correct meaning here (arrivals within a window vs
        ## stays overlapping one), so the schema requires the pair.
        if from_date and to_date:
            query = query.filter(
                Reservation.check_in_date <= to_date,
                Reservation.check_out_date >= from_date
            )

        ## Status filter. The value comes from the reservation_status enum table and is
        ## validated in the request schema, but normalising here as well means a
        ## stray capital cannot silently return zero rows.
        if reservation_status:
            try:
                normalised_status = self.enums.normalise(
                    reservation_status, RESERVATION_STATUS_ENUM_KEY
                )
            except EnumUnavailableError as exc:
                logger.error("ReservationService.get_all_reservations: %s", exc)
                return service_response(False, str(exc), None, 503)

            if normalised_status is None:
                return service_response(False, "Invalid reservation status filter.", None, 400)

            query = query.filter(Reservation.reservation_status == normalised_status)

        ## Room number filter
        if room_number:
            search = f"{room_number}%"
            query = query.filter(Room.room_number.like(search))

        ## Pagination
        total_records = query.count()

        reservations = (
            query
            .order_by(Reservation.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        ## Response formatting
        reservations_list = [
            {
                "reservation_id": reservation.id,
                "room_id": reservation.room_id,
                "reservation_number": reservation.reservation_number,
                "room_number": reservation.room.room_number,
                "total_amount": reservation.total_amount,
                "total_nights": reservation.total_nights,
                "reservation_status": reservation.reservation_status,
                "check_in_date": reservation.check_in_date,
                "check_out_date": reservation.check_out_date,
                "created_by": ReservationService._actor_name(reservation.created_by_user),
                "created_at": reservation.created_at
            }
            for reservation in reservations
        ]

        last_page = (total_records + page_size -1) // page_size if total_records > 0 else 1

        return {
            "status": True,
            "data": reservations_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200


    def get_available_rooms(self, data: dict):
        check_in = data.get("check_in")
        check_out = data.get("check_out")
        room_type_id = data.get("room_type_id")
        page_size = data["page_size"]
        page_number = data["page_number"]

        ## The bookable room status is the room_status option flagged `is_default`,
        ## not a literal in this file: an operator who renames that state or
        ## marks a different one as the bookable default changes the picker
        ## without a deploy.
        ##
        ## An unreachable enum table must not return every room in the house as
        ## bookable -- that is the worst possible failure here, since the guest
        ## would only discover the clash when the booking is submitted. Fail the
        ## picker instead.
        try:
            bookable_status = self.enums.default_value(ROOM_STATUS_ENUM_KEY)
        except EnumUnavailableError as exc:
            logger.error("ReservationService.get_available_rooms: %s", exc)
            return service_response(False, str(exc), None, 503)

        query = (
            self.db.query(Room)
            .options(joinedload(Room.room_type))
            .filter(
                Room.is_deleted == False,
                Room.is_active == True,
                Room.room_status == bookable_status
            )
        )

        if room_type_id:
            query = query.filter(Room.room_type_id == room_type_id)

        ## Date-based availability filters (Apply only if both dates exist)
        if check_in and check_out:
            reservation_exists = exists().where(
                and_(
                    Reservation.room_id == Room.id,
                    ## Cancelled bookings release the room, so they must not
                    ## hide it from the picker.
                    *ReservationService._live_reservation_filters(),
                    *ReservationService._reservation_overlap(check_in, check_out)
                )
            )

            ## Blocked rooms overlapping
            block_exists = exists().where(
                and_(
                    RoomBlocks.room_id == Room.id,
                    RoomBlocks.is_deleted == False,
                    *ReservationService._block_overlap(check_in, check_out)
                )
            )

            query = query.filter(
                not_(reservation_exists),
                not_(block_exists)
            )

        ## Pagination
        total_records = query.count()

        rooms = (
            query
            .order_by(Room.id.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        ## Response formatting
        rooms_list = []
        for room in rooms:
            room_amenities = [
                rta.room_amenity.name
                for rta in room.room_type.room_amenities
                if rta.room_amenity.is_active
            ]

            rooms_list.append({
                "room_id": room.id,
                "room_number": room.room_number,
                "room_type": room.room_type.name,
                "price": room.room_type.base_price,
                "max_adults": room.room_type.max_adults,
                "max_children": room.room_type.max_children,
                "max_infants": room.room_type.max_infants,
                "extra_bed_allowed": room.room_type.extra_bed_allowed,
                "extra_bed_price": room.room_type.extra_bed_price,
                "room_amenities": room_amenities
            })

        last_page = (total_records + page_size - 1) // page_size

        return {
            "status": True,
            "data": rooms_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200


    def create_reservation(self, data: dict):
        room_id = data.get("room_id")
        if not room_id:
            return service_response(False, "Field room_id is required", None, 400)

        try:
            check_in, check_out = ReservationService._parse_stay_dates(data)
        except ValueError as exc:
            return service_response(False, str(exc), None, 400)

        total_adults = data.get("total_adults", 0)
        total_children = data.get("total_children", 0)
        total_infants = data.get("total_infants", 0)

        ## Validate room
        room_exists = self.db.query(
            exists().where(
                and_(
                    Room.id == room_id,
                    Room.is_deleted == False,
                    Room.is_active == True
                )
            )
        ).scalar()
        if not room_exists:
            return service_response(False, "Room not found or inactive.", None, 404)

        ## Check overlapping reservation
        reservation_conflict = self.db.query(
            exists().where(
                and_(
                    Reservation.room_id == room_id,
                    *ReservationService._live_reservation_filters(),
                    *ReservationService._reservation_overlap(check_in, check_out)
                )
            )
        ).scalar()
        if reservation_conflict:
            return {"status": False, "message": "Room is already booked for selected dates."}, 409

        ## Check overlapping blocks
        block_conflict = self.db.query(
            exists().where(
                and_(
                    RoomBlocks.room_id == room_id,
                    RoomBlocks.is_deleted == False,
                    *ReservationService._block_overlap(check_in, check_out)
                )
            )
        ).scalar()
        if block_conflict:
            return {"status": False, "message": "Room is blocked for selected dates."}, 409

        room = self.db.get(Room, room_id)
        if not room or not room.room_type:
            return service_response(False, "Room or Room Type details missing.", None, 409)

        # --- Capacity Validation ---
        max_adults = room.room_type.max_adults
        max_children = room.room_type.max_children
        max_infants = room.room_type.max_infants
        max_capacity = max_adults + max_children
        total_guests = total_adults + total_children

        # 1. Strict check: Adults cannot exceed max allowed adults
        if total_adults > max_adults:
            return service_response(
                False,
                f"Exceeded adult limit. Maximum allowed adults for this room is {max_adults}.",
                None,
                422
            )

        # 2. Flexible check: Total guests cannot exceed total room capacity
        if total_guests > max_capacity:
            return service_response(
                False,
                f"Exceeded total room capacity. Maximum allowed guests for this room is {max_capacity}.",
                None,
                422
            )

        if total_infants > max_infants:
            return service_response(
                False,
                f"Exceeded infant limit. Maximum allowed infants for this room is {max_infants}.",
                None,
                422
            )

        ## --- Date & Pricing Calculations ---
        ## nights == 0 is a same-day booking, not an error: it is stored as-is
        ## and charged one full night.
        nights = (check_out - check_in).days
        if nights < 0:
            return service_response(False, "Invalid check-in/check-out dates.", None, 422)

        total_amount = ReservationService._calculate_amount(nights, room.room_type.base_price)

        ## Create Reservation Number
        sequence_service = ReservationSequenceService(self.db)
        reservation_number = sequence_service.generate()

        ## A new booking opens at the reservation_status option flagged `is_default`,
        ## so the starting state is a data change rather than a literal here.
        try:
            opening_status = self.enums.default_value(RESERVATION_STATUS_ENUM_KEY)
        except EnumUnavailableError as exc:
            logger.error("ReservationService.create_reservation: %s", exc)
            return service_response(False, str(exc), None, 503)

        reservation = Reservation(
            room_id=room_id,
            reservation_number=reservation_number,
            check_in_date=check_in,
            check_out_date=check_out,
            total_amount=total_amount,
            total_nights=nights,
            reservation_status=opening_status,
            created_by=data.get("created_by") or 1,
            total_adults=total_adults,
            total_children=total_children,
            total_infants=total_infants
        )
        self.db.add(reservation)
        self.db.flush()
        return service_response(True, "Reservation created successfully.", {"reservation_id": reservation.id}, 201)


    def create_reservation_upsert_guest(self, data):
        guest_details = data.get("guest_details") or {}
        reservation_details = dict(data.get("reservation_details") or {})

        if not reservation_details:
            return service_response(False, "reservation_details is required", None, 400)

        additional_guests = guest_details.get("additional_guests") or []

        ## Counts are derived from the additional guests' ages, not trusted from
        ## the payload -- otherwise a client could post total_adults=0 and
        ## bypass the occupancy checks below.
        adults, children, infants = ReservationService._count_guests(additional_guests)
        reservation_details["total_adults"] = adults
        reservation_details["total_children"] = children
        reservation_details["total_infants"] = infants

        reservation_result = self.create_reservation(reservation_details)
        if not reservation_result or not reservation_result[0]["status"]:
            self.db.rollback()
            return reservation_result or service_response(
                False, "Reservation could not be created", None, 422
            )

        reservation_id = reservation_result[0]["data"]["reservation_id"]

        ## One transaction for the booking, the guest, and the guest link. The
        ## old version committed the reservation via create_reservation's caller
        ## and then rolled back on guest failure, so a partial failure could
        ## leave an orphaned reservation row behind.
        guest_upsert_result = self.guest_service.upsert_guest(guest_details)
        if not guest_upsert_result or not guest_upsert_result[0]["status"]:
            self.db.rollback()
            return guest_upsert_result or service_response(
                False, "Guest upsert failed", None, 422
            )

        if additional_guests:
            self.guest_service.handle_additional_guests(reservation_id, additional_guests)

        ## Only link when absent. An existing link means this booking already has
        ## a primary guest, and re-adding would duplicate the association.
        if not self.db.query(ReservationPrimaryGuest).filter_by(
            reservation_id=reservation_id
        ).first():
            self.db.add(ReservationPrimaryGuest(
                reservation_id=reservation_id,
                primary_guest_id=guest_upsert_result[0]["data"]["guest_id"]
            ))

        self.db.commit()

        return service_response(
            True,
            "Reservation created successfully.",
            {"reservation_id": reservation_id},
            201,
        )

    def update_reservation(self, data: dict):
        reservation_id = data.get("reservation_id")
        room_id = data.get("room_id")
        if not reservation_id:
            return service_response(False, "Field reservation_id is required", None, 400)
        if not room_id:
            return service_response(False, "Field room_id is required", None, 400)

        try:
            check_in, check_out = ReservationService._parse_stay_dates(data)
        except ValueError as exc:
            return service_response(False, str(exc), None, 400)

        total_amount_override = data.get("total_amount_override", False)
        total_amount_override_reason = data.get("total_amount_override_reason", "") or ""

        ## 1. Validate dates
        nights = (check_out - check_in).days
        if nights < 0:
            return service_response(False, "Invalid check-in/check-out dates.", None, 422)

        ## 2. Get existing reservation
        reservation = self.db.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.is_deleted == False
        ).first()
        if not reservation:
            return service_response(False, "Reservation not found.", None, 404)

        ## Optional: don't allow update of cancelled reservation
        if reservation.reservation_status == STATUS_CANCELLED:
            return service_response(False, "Cancelled reservation cannot be updated.", None, 422)

        ## 3. Validate room
        room_exists = self.db.query(
            exists().where(
                and_(
                    Room.id == room_id,
                    Room.is_deleted == False,
                    Room.is_active == True
                )
            )
        ).scalar()
        if not room_exists:
            return service_response(False, "Room not found or inactive.", None, 404)

        ## 4. Check overlapping reservation
        ## IMPORTANT: exclude current reservation
        reservation_conflict = self.db.query(
            exists().where(
                and_(
                    Reservation.room_id == room_id,
                    Reservation.id != reservation_id,  ## IMPORTANT
                    *ReservationService._live_reservation_filters(),
                    *ReservationService._reservation_overlap(check_in, check_out)
                )
            )
        ).scalar()
        if reservation_conflict:
            return service_response(False, "Room is already booked for selected dates.", None, 409)

        ## 5. Check overlapping room blocks
        block_conflict = self.db.query(
            exists().where(
                and_(
                    RoomBlocks.room_id == room_id,
                    RoomBlocks.is_deleted == False,

                    *ReservationService._block_overlap(check_in, check_out)
                )
            )
        ).scalar()
        if block_conflict:
            return service_response(False, "Room is blocked for selected dates.", None, 409)

        ## 6. Get room + room type
        room = self.db.get(Room, room_id)
        if not room or not room.room_type:
            return service_response(False, "Room or Room Type details missing.", None, 409)

        ## 7. Calculate amount
        ## Same-day stays (nights == 0) are charged one full night.
        calculated_amount = ReservationService._calculate_amount(nights, room.room_type.base_price)

        ## 8. Handle amount override
        if total_amount_override:
            if not data.get("total_amount"):
                return service_response(
                    False,
                    "Total amount is required when amount override is enabled.",
                    None,
                    422
                )

            if not total_amount_override_reason.strip():
                return service_response(
                    False,
                    "Override reason is required when amount override is enabled.",
                    None,
                    422
                )

            total_amount = Decimal(str(data["total_amount"]))

        else:
            total_amount = calculated_amount
            ## Clear override reason if override is disabled
            total_amount_override_reason = ""

        ## 9. Update reservation
        reservation.room_id = room_id
        reservation.check_in_date = check_in
        reservation.check_out_date = check_out
        reservation.total_nights = nights
        reservation.total_amount = total_amount

        ## Persisted columns -- previously these assignments silently created
        ## undeclared instance attributes that were discarded on flush, so the
        ## override was accepted and then lost on every request.
        reservation.total_amount_override = bool(total_amount_override)
        reservation.total_amount_override_reason = total_amount_override_reason or None

        self.db.commit()
        return service_response(True, "Reservation updated successfully.", None, 200)


    def update_guests(self, data: dict):
        guest_details = data.get("guest_details") or {}
        reservation_id = data.get("reservation_id")
        if not reservation_id:
            return service_response(False, "Field reservation_id is required", None, 400)

        ## Same age bands as the create path -- see `_count_guests`.
        adults, children, infants = ReservationService._count_guests(
            guest_details.get("additional_guests") or []
        )

        ## 1. Get existing reservation
        reservation = self.db.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.is_deleted == False
        ).first()
        if not reservation:
            return service_response(False, "Reservation not found.", None, 404)

        ## 2. Get room + room type
        room = self.db.get(Room, reservation.room_id)
        if not room or not room.room_type:
            return service_response(
                False,
                "Room or Room Type details missing.",
                None,
                409
            )

        ## 3. Capacity validation, shared with the create path so the two cannot drift
        max_adults = room.room_type.max_adults
        max_children = room.room_type.max_children
        max_infants = room.room_type.max_infants
        max_capacity = max_adults + max_children
        total_guests = adults + children

        if adults > max_adults:
            return service_response(
                False,
                f"Exceeded adult limit. Maximum allowed adults for this room is {max_adults}.",
                None,
                422
            )

        if total_guests > max_capacity:
            return service_response(
                False,
                f"Exceeded total room capacity. Maximum allowed guests for this room is {max_capacity}.",
                None,
                422
            )

        if infants > max_infants:
            return service_response(
                False,
                f"Exceeded infant limit. Maximum allowed infants for this room is {max_infants}.",
                None,
                422
            )

        reservation.total_adults = adults
        reservation.total_children = children
        reservation.total_infants = infants

        ## Nothing is committed until the guest upsert succeeds, so a rejected
        ## id_type cannot leave the counts updated against a half-saved booking.
        guest_upsert_result = self.guest_service.upsert_guest(guest_details)
        if not guest_upsert_result or not guest_upsert_result[0]["status"]:
            self.db.rollback()
            return guest_upsert_result or service_response(
                False, "Guest upsert failed", None, 422
            )

        additional_guests = guest_details.get("additional_guests") or []
        if additional_guests:
            self.guest_service.handle_additional_guests(reservation_id, additional_guests)

        self.db.commit()
        return service_response(True, "Reservation guests updated successfully.", None, 200)



    def delete_reservation(self, reservation_id):
        reservation = self.db.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.is_deleted == False
        ).first()
        if not reservation:
            return service_response(False, "Reservation not found or already deleted.", None, 422)
        reservation.is_deleted = True
        reservation.deleted_at = datetime.now()
        self.db.commit()
        return service_response(True, "Reservation deleted successfully.", None, 200)


    def cancel_reservation(self, reservation_id, data: dict):
        """Cancel a booking and record who/when/why.

        `data` carries `cancellation_reason` and `cancelled_by`. The latter is
        supplied by the route from the auth token -- never from the client, so
        nobody can assert a different user cancelled their own booking.
        """
        reservation = self.db.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.is_deleted == False
        ).first()
        if not reservation:
            return service_response(False, "Reservation not found or already deleted.", None, 404)

        ## Idempotency guard: a second cancel would overwrite the original
        ## reason and cancelled_by, destroying the audit trail this exists for.
        if reservation.reservation_status == STATUS_CANCELLED:
            return service_response(
                False,
                "Reservation is already cancelled.",
                {"cancelled_at": reservation.cancelled_at.isoformat() if reservation.cancelled_at else None},
                409
            )

        if reservation.reservation_status not in CANCELLABLE_STATUSES:
            return service_response(
                False,
                f"A reservation with status '{reservation.reservation_status}' cannot be cancelled.",
                None,
                422
            )

        reason = str(data.get("cancellation_reason") or "").strip()
        if not reason:
            return service_response(
                False,
                "Cancellation reason is required.",
                None,
                422
            )
        if len(reason) > MAX_CANCELLATION_REASON:
            return service_response(
                False,
                f"Cancellation reason must be {MAX_CANCELLATION_REASON} characters or fewer.",
                None,
                422
            )

        ## Money already taken against this booking. Cancelling does NOT refund
        ## it -- refunds are recorded separately -- so the amount is returned to
        ## the caller, which surfaces it to the operator as a follow-up action
        ## rather than letting a cancelled booking hide a liability.
        ##
        ## `paid_total += amount`, not `-= amount`. Subtracting here made the
        ## running total negative for every booking that had taken a payment, so
        ## `refund_required = paid_total > 0` below was ALWAYS False: the API
        ## reported no refund due even when a guest had paid an advance. The
        ## sign here and the comparison there have to agree; money collected is
        ## positive, and "a refund is due" means positive.
        paid_total = Decimal('0')
        for payment in reservation.payments or []:
            if payment.is_deleted:
                continue
            paid_total += Decimal(str(payment.amount or 0))

        reservation.reservation_status = STATUS_CANCELLED
        reservation.cancellation_reason = reason
        reservation.cancelled_at = datetime.utcnow()
        reservation.cancelled_by = data.get("cancelled_by")
        self.db.commit()

        return service_response(
            True,
            "Reservation cancelled successfully.",
            {
                "reservation_id": reservation.id,
                "reservation_status": reservation.reservation_status,
                "cancellation_reason": reservation.cancellation_reason,
                "cancelled_at": reservation.cancelled_at.isoformat(),
                ## surfaced so the UI can tell the operator a refund is due
                "paid_total": float(paid_total),
                "refund_required": paid_total > 0
            },
            200
        )

    def get_reservation_by_id(self, reservation_id):
        reservation = self.db.query(Reservation).options(
            joinedload(Reservation.room).joinedload(Room.room_type),
            joinedload(Reservation.primary_guest_link)
            .joinedload(ReservationPrimaryGuest.guest)
            .options(
                joinedload(Guest.city),
                joinedload(Guest.state),
                joinedload(Guest.country)
            ),
            selectinload(Reservation.additional_guest_link).joinedload(ReservationAdditionalGuest.additional_guest),
            joinedload(Reservation.created_by_user),
            ## Plain load -- ordering is done below in Python. `selectinload` returns a
            ## base `Load` in SQLAlchemy 2.0 with no `order_by`, and a NULL
            ## paid_at also sorts unpredictably in SQL across backends, so the
            ## sort has to be explicit to be reproducible anyway.
            selectinload(Reservation.payments)
        ).filter(
            Reservation.id == reservation_id,
            Reservation.is_deleted == False
        ).first()

        if not reservation:
            return service_response(False, "Reservation not found.", None, 422)

        # 2. Extract references safely to avoid long chain expressions
        room = reservation.room
        guest_link = reservation.primary_guest_link
        guest = guest_link.guest if guest_link else None

        # 3. Handle potential serialization issues safely
        def to_iso(dt):
            return dt.isoformat() if hasattr(dt, 'isoformat') else dt

        ## 4. Process additional guests collection and compute guest counts
        adult = 1  # Primary guest counts as 1 adult by default
        children = 0
        infants = 0
        additional_guests = []

        for link in reservation.additional_guest_link or []:
            if not (link and link.additional_guest):
                continue

            additional_guest = link.additional_guest
            age = getattr(additional_guest, "age", None)

            ## Same `_classify_age` bands the write paths use. This block was a
            ## third, separately-typed copy of the thresholds, so a read could
            ## classify a guest differently from the write that stored them.
            band = ReservationService._classify_age(age)
            if band == "infant":
                infants += 1
            elif band == "child":
                children += 1
            else:
                adult += 1

            additional_guests.append(
                {
                    "id": additional_guest.id,
                    "full_name": getattr(additional_guest, "full_name", None),
                    "gender": getattr(additional_guest, "gender", None),
                    "age": age,
                    "id_type": getattr(additional_guest, "id_type", None),
                    "id_number": getattr(additional_guest, "id_number", None),
                }
            )

        ## Full ledger, newest first. This replaces the old single-row
        ## `advance_payment` aggregate, which could only ever describe the
        ## first advance and was the only payment data the response used to
        ## carry -- so every additional advance and refund was invisible to
        ## clients. Clients derive paid total / balance from this array.
        ##
        ## Refunds carry a positive amount and are flagged rather than signed:
        ## clients subtract them, so sending a negative would make any client
        ## that also subtracts double-count them.
        live_payments = [p for p in (reservation.payments or []) if not p.is_deleted]
        ## Newest first. `paid_at` is nullable, so fall back to the booking row
        ## timestamp, then to the epoch; `id` breaks ties so same-day
        ## instalments keep a stable order rather than whatever the DB
        ## happened to hand back.
        live_payments.sort(
            key=lambda p: (p.paid_at or p.created_at or datetime.min, p.id or 0),
            reverse=True
        )

        payments = []
        for payment in live_payments:
            payments.append({
                "id": payment.id,
                "reservation_id": payment.reservation_id,
                # "folio_id": payment.folio_id,
                "payment_type": str(getattr(payment.payment_type, "value", payment.payment_type)),
                "amount": float(payment.amount) if payment.amount is not None else 0.0,
                "currency": payment.currency,
                "base_amount": float(payment.base_amount) if payment.base_amount is not None else None,
                "exchange_rate": float(payment.exchange_rate) if payment.exchange_rate is not None else None,
                "payment_method": str(getattr(payment.payment_method, "value", payment.payment_method)),
                "payment_status": str(getattr(payment.payment_status, "value", payment.payment_status)),
                "transaction_ref": payment.transaction_ref,
                "remarks": payment.remarks,
                "paid_at": to_iso(payment.paid_at) or to_iso(payment.created_at),
                "verified_at": to_iso(payment.verified_at)
            })

        # 5. Construct cleaner, structured response data
        reservation_data = {
            "id": reservation.id,
            "reservation_number": reservation.reservation_number,
            "reservation_status": reservation.reservation_status,
            "cancellation_reason": reservation.cancellation_reason,
            "cancelled_at": to_iso(reservation.cancelled_at),
            "room_id": reservation.room_id,
            "check_in_date": to_iso(reservation.check_in_date),
            "check_out_date": to_iso(reservation.check_out_date),
            "total_amount": float(reservation.total_amount) if reservation.total_amount else 0.0,
            "total_amount_override": bool(reservation.total_amount_override),
            "total_amount_override_reason": reservation.total_amount_override_reason or "",
            "total_nights": reservation.total_nights,
            "created_by": reservation.created_by_user.first_name + " " + reservation.created_by_user.last_name,
            "created_at": to_iso(reservation.created_at),
            "updated_at": to_iso(reservation.updated_at),
            "payments": payments,
            "adults_count": adult,
            "children_count": children,
            "infants_count": infants,

            "room": {
                "room_number": room.room_number if room else None,
                "room_type": room.room_type.name if room and room.room_type else None,
            },

            "primary_guest": {
                "id": guest.id,
                "first_name": guest.first_name,
                "last_name": guest.last_name,
                "gender": guest.gender,
                "date_of_birth": to_iso(guest.date_of_birth),
                "email": guest.email,
                "phone_number": guest.phone_number,
                "address": guest.address,
                "city": guest.city.name if guest.city else None,
                "state": guest.state.name if guest.state else None,
                "country": guest.country.name if guest.country else None,
                "nationality": guest.country.nationality if guest.country else None,
                "id_type": guest.id_type,
                "id_number": guest.id_number,
                "notes": guest.notes,
                "vip_status": guest.vip_status,
                "blacklist_status": guest.blacklist_status,
            } if guest else None,
            "additional_guests": additional_guests
        }

        return service_response(True, "Reservation fetched successfully.", reservation_data, 200)


    def insert_reservation_payment(self, data: dict):
        reservation_id = data.get("reservation_id")
        if not reservation_id:
            return service_response(False, "Field reservation_id is required", None, 400)

        reservation_details = self.db.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.is_deleted == False,
        ).first()
        if not reservation_details:
            return service_response(False, "Reservation not found.", None, 422)

        if reservation_details.reservation_status == STATUS_CANCELLED:
            return service_response(
                False,
                "Cannot record a payment against a cancelled reservation.",
                None,
                422,
            )

        payment_insertion_result = self.payment_service.insert_payment_details(data)
        if not payment_insertion_result or not payment_insertion_result[0]["status"]:
            return payment_insertion_result

        ## Recording a payment moves an untouched booking to `reserved`. Only the
        ## opening state is transitioned: a booking that has already been
        ## reserved (a follow-up instalment) or checked in stays where it is,
        ## so a late payment cannot drag a live stay backwards.
        try:
            opening_status = self.enums.default_value(RESERVATION_STATUS_ENUM_KEY)
        except EnumUnavailableError as exc:
            self.db.rollback()
            logger.error("ReservationService.insert_reservation_payment: %s", exc)
            return service_response(False, str(exc), None, 503)

        if reservation_details.reservation_status == opening_status:
            reservation_details.reservation_status = STATUS_RESERVED

        self.db.commit()
        return service_response(
            True,
            "Payment recorded successfully.",
            {"reservation_id": reservation_details.id},
            200,
        )
