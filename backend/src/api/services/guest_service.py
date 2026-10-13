import logging

from src.api.utils.responses import service_response
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from src.api.models import Guest, AdditionalGuest, ReservationAdditionalGuest
from src.api.models.enum_definitions_model import EnumDefinition
from src.api.models.enum_options_model import EnumOption


logger = logging.getLogger(__name__)


## `enum_definitions.enum_key` backing each enum column written by this service.
## Both come from enum_seeder.py and are the ONLY definition of the allowed
## values -- nothing is hardcoded here, so adding an option is a data change.
GUEST_ID_TYPE_ENUM_KEY = "guests_id_type"
GENDER_ENUM_KEY = "gender"


class GuestService:
    def __init__(self, db):
        self.db = db
        self._enum_cache: dict[str, tuple[str, ...]] = {}

    @staticmethod
    def _parse_date(value):
        """Normalize a date coming from the client (str | date | datetime) to a date object."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


    def get_all_guests(self, data:dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = data.get("search_value")
        query = (
            self.db.query(Guest)
            .options(joinedload(Guest.nationality))
            .filter(Guest.is_deleted == False)
        )
        if search_value:
            val = search_value.strip()
            query = query.filter(Guest.email.like(f"{val}%"))

        total_records = query.count()
        guests = (
            query
            .order_by(Guest.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )
        guest_list = [
            {
                "id": guest.id,
                "first_name": guest.first_name,
                "last_name": guest.last_name,
                "gender": guest.gender,
                "date_of_birth": guest.date_of_birth,
                "email": guest.email,
                "phone_number": guest.phone_number,
                "address": guest.address,
                "city_id": guest.city_id,
                "state_id": guest.state_id,
                "country_id": guest.country_id,
                "id_type": guest.id_type,
                "id_number": guest.id_number,
                "nationality": guest.nationality.nationality if guest.nationality else None,
                "vip_status": guest.vip_status,
                "blacklist_status": guest.blacklist_status,
                "notes": guest.notes,
                "is_active": guest.is_active
            }
            for guest in guests
        ]
        last_page = (total_records + page_size - 1) // page_size if total_records > 0 else 1
        return {
            "status": True,
            "data": guest_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200


    def get_guest_by_id(self, guest_id):
        guest = self.db.query(Guest).filter_by(is_deleted=False, id=guest_id).first()
        if not guest:
            return service_response(False, "Guest not found", None, 404)
        guest_data = {
            "id": guest.id,
            "first_name": guest.first_name,
            "last_name": guest.last_name,
            "gender": guest.gender,
            "date_of_birth": guest.date_of_birth,
            "email": guest.email,
            "phone_number": guest.phone_number,
            "address": guest.address,
            "city_id": guest.city_id,
            "state_id": guest.state_id,
            "country_id": guest.country_id,
            "id_type": guest.id_type,
            "id_number": guest.id_number,
            "nationality_id": guest.nationality_id,
            "vip_status": guest.vip_status,
            "blacklist_status": guest.blacklist_status,
            "notes": guest.notes,
            "is_active": guest.is_active,
            "is_deleted": guest.is_deleted,
            "created_at": guest.created_at.isoformat()
        }
        return service_response(True, "Guest fetched successfully.", guest_data, 200)


    def upsert_guest(self, data: dict):
        ## Partial payloads are valid here (e.g. the delete call only sends the flags),
        ## so read defensively instead of indexing.
        guest_id = data.get("id", 0)
        guest_email = data.get("email")

        is_deleted_op = data.get("is_deleted") is True

        ## Enum-backed columns are validated up front so the blind setattr loop
        ## further down cannot write an arbitrary string. Skipped entirely on a
        ## delete: that payload carries only the flags, and a soft-deleted row
        ## must stay deletable even if its stored value is no longer an option.
        normalised = {}
        if not is_deleted_op:
            try:
                for field, enum_key in (
                    ("id_type", GUEST_ID_TYPE_ENUM_KEY),
                    ("gender", GENDER_ENUM_KEY),
                ):
                    if field not in data:
                        continue

                    value = self._normalise_enum(data[field], enum_key)
                    if value is None:
                        return service_response(
                            False,
                            f"Unknown {field} '{data[field]}'.",
                            None,
                            400,
                        )
                    normalised[field] = value
            except LookupError as exc:
                ## An unseeded / unreachable enum table is an infrastructure
                ## fault, not bad input. Say so instead of returning a 500.
                logger.error("GuestService.upsert_guest: %s", exc)
                return service_response(False, str(exc), None, 503)

        if guest_email and not is_deleted_op:
            duplicate_check = self.db.query(Guest).filter(
                Guest.is_deleted == False,
                Guest.email == guest_email,
                Guest.id != guest_id
            ).first()
            if duplicate_check:
                return service_response(False, "Guest with this email already exists", None, 409)

        if guest_id == 0:
            REQUIRED_FIELDS = (
                "first_name",
                "last_name",
                "gender",
                "date_of_birth",
                "email",
                "phone_number",
                "country_id",
                "state_id",
                "city_id",
                "id_type",
                "id_number",
                "nationality_id",
                # "vip_status",
                # "blacklist_status",
                # "is_active"
            )
            for field in REQUIRED_FIELDS:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required", None, 400)

            guest = Guest()
            self.db.add(guest)
            message = "Guest created successfully."
            status_code = 201
        else:
            guest = self.db.query(Guest).filter_by(is_deleted=False, id=guest_id).first()
            if not guest:
                return service_response(False, "Guest not found", None, 404)

            message = "Guest updated successfully."
            status_code = 200

        FIELDS = (
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "email",
            "phone_number",
            "address",
            "country_id",
            "state_id",
            "city_id",
            "id_type",
            "id_number",
            "nationality_id",
            "notes",
            "vip_status",
            "blacklist_status",
            "is_active",
            "is_deleted"
        )
        for field in FIELDS:
            if field in data:
                setattr(guest, field, data[field])

        ## Normalised above, so the stored value is always a current option.
        for field, value in normalised.items():
            setattr(guest, field, value)

        if "date_of_birth" in data and data["date_of_birth"]:
            guest.date_of_birth = self._parse_date(data["date_of_birth"])

        self.db.flush()

        if is_deleted_op:
            message = "Guest deleted successfully."

        self.db.commit()
        self.db.refresh(guest)
        return service_response(True, message, {"guest_id": guest.id}, status_code)


    def handle_additional_guests(self, reservation_id, additional_guests_data):
        self.db.query(ReservationAdditionalGuest).filter(
            ReservationAdditionalGuest.reservation_id == reservation_id
        ).delete()

        for item in additional_guests_data:
            new_guest = AdditionalGuest(
                full_name=item.get("full_name"),
                gender=item.get("gender"),
                age=item.get("age"),
                id_type=item.get("id_type") or None,
                id_number=item.get("id_number") or None
            )
            self.db.add(new_guest)
            self.db.flush()

            link = ReservationAdditionalGuest(
                reservation_id=reservation_id,
                additional_guest_id=new_guest.id
            )
            self.db.add(link)


    # ---------------------------------------------------------------
    # ENUM HELPERS
    # ---------------------------------------------------------------

    def _valid_enum_values(self, enum_key: str) -> tuple[str, ...]:
        """Active option keys for one enum definition, read once per instance.

        Raises on an unreachable or unseeded table rather than falling back to a
        hardcoded list: a second source of truth in this file would drift from
        `enum_seeder.py`, which is exactly the problem the enum tables exist to
        solve. An admin adding an option must be enough.
        """
        if enum_key not in self._enum_cache:
            definition = (
                self.db.query(EnumDefinition)
                .filter(
                    EnumDefinition.enum_key == enum_key,
                    EnumDefinition.is_deleted == False,
                )
                .first()
            )
            if not definition:
                raise LookupError(
                    f"Enum definition '{enum_key}' is missing. Run the enum seeder."
                )

            options = (
                self.db.query(EnumOption)
                .filter(
                    EnumOption.enum_id == definition.id,
                    EnumOption.is_deleted == False,
                    EnumOption.is_active == True,
                )
                .order_by(EnumOption.sort_order.asc())
                .all()
            )
            if not options:
                raise LookupError(
                    f"Enum definition '{enum_key}' has no active options."
                )

            self._enum_cache[enum_key] = tuple(
                str(option.option_key).strip().lower() for option in options
            )

        return self._enum_cache[enum_key]

    def _normalise_enum(self, value, enum_key: str) -> str | None:
        """Bare value for the String column, or None when not an allowed option."""
        if value is None:
            return None

        text = str(getattr(value, "value", value)).strip().lower()
        if not text:
            return None

        return text if text in self._valid_enum_values(enum_key) else None








