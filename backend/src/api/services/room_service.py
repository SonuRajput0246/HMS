import logging
from sqlalchemy.orm import joinedload
from src.api.models import Room, RoomType
from src.api.utils.responses import service_response
from src.api.models.enum_definitions_model import EnumDefinition


logger = logging.getLogger(__name__)

## `enum_definitions.enum_key` backing `rooms.room_status`.
ROOM_STATUS_ENUM_KEY = "room_status"

## Always accepted, whatever the enum table says. `available` is what
## reservation_service filters on to find bookable rooms, so it must never be
## lost to a bad seed. `reserved` and `occupied` are included because
## room_schema.UpsertRoomSchema still accepts them even though enum_seeder does
## not define them -- see the note on _load_room_statuses below.
CORE_ROOM_STATUSES = (
    "available",
    "cleaning",
    "maintenance",
    "out_of_service",
)


class RoomService:

    def __init__(self, db):
        self.db = db
        self._room_status_cache: tuple[str, ...] | None = None


    def get_room_types(self):
        room_types = (
            self.db.query(RoomType)
            .filter(
                RoomType.is_deleted == False,
                RoomType.is_active == True
            )
            .order_by(RoomType.base_price.asc())
            .all()
        )

        data = [
            {
                "id": rt.id,
                "name": rt.name,
                "description": rt.description,
                "base_price": rt.base_price,
                "max_adults": rt.max_adults,
                "max_children": rt.max_children,
                "extra_bed_allowed": rt.extra_bed_allowed,
                "extra_bed_price": rt.extra_bed_price
            }
            for rt in room_types
        ]

        return {
            "status": True,
            "data": data
        }, 200



    def get_all_rooms(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        room_type_id = data.get("room_type_id")
        search_value = data.get("search_value")
        query = (
            self.db.query(Room)
                .options(joinedload(Room.room_type))
                .filter(Room.is_deleted == False)
        )
        if room_type_id:
            query = query.filter(Room.room_type_id == room_type_id)

        if search_value:
            val = search_value.strip()
            query = query.filter(Room.room_number.like(f"{val}%"))

        total_records = query.count()

        rooms = (
            query
            .order_by(Room.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )
        rooms_list = [
            {
                "id": room.id,
                "room_number": room.room_number,
                "room_type_id": room.room_type_id,
                "room_type_name": room.room_type.name if room.room_type else "N/A",
                "floor_number": room.floor_number,
                ## Plain String column -- emit the value itself.
                "room_status": room.room_status,
                "view": room.view,
                "notes": room.notes,
                "is_active": room.is_active
            }
            for room in rooms
        ]
        last_page = (total_records + page_size -1) // page_size if total_records > 0 else 1
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


    def get_room_by_id(self, room_id):
        room = (
            self.db.query(Room)
            .options(joinedload(Room.room_type))
            .filter(Room.is_deleted==False, Room.id == room_id).first()
        )
        if not room:
            return service_response(False, "Room not found", None, 404)
        room_data = {
            "id": room.id,
            "room_number": room.room_number,
            "room_type_id": room.room_type_id,
            "room_type_name": room.room_type.name if room.room_type else "Unknown",
            "floor_number": room.floor_number,
            "room_status": room.room_status,
            "view": room.view,
            "notes": room.notes,
            "is_active": room.is_active
        }
        return service_response(True, "Room fetched successfully.", room_data, 200)


    def upsert_room(self, data: dict):
        ## `.get` rather than `data[...]`: a missing key used to raise KeyError
        ## inside the service, which the route surfaced as a 500.
        room_id = data.get('id', 0)
        room_number = data.get('room_number')
        is_delete_op = data.get('is_deleted') is True

        ## `room_status` is an enum-backed String column. Validated before the
        ## field loop below, which would otherwise write any string through.
        room_status = self._normalise_room_status(data.get("room_status"))
        if room_status is None and "room_status" in data:
            return service_response(
                False,
                f"Unknown room_status '{data.get('room_status')}'. Allowed values: "
                + ", ".join(self._valid_room_statuses())
                + ".",
                None,
                400,
            )

        if room_number and not is_delete_op:
            duplicate_check = self.db.query(Room).filter(
                Room.is_deleted == False,
                Room.room_number == room_number,
                Room.id != room_id
            ).first()
            if duplicate_check:
                return service_response(False, "Room with this number already exists.", None, 409)

        if room_id == 0:
            REQUIRED_FIELDS = ("room_number", "room_type_id", "floor_number", "room_status")
            for field in REQUIRED_FIELDS:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required", None, 400)

            room = Room()
            self.db.add(room)
            message = "Room created successfully."
            status_code = 201
        else:
            room = self.db.query(Room).filter(Room.is_deleted==False, Room.id == room_id).first()
            if not room:
                return service_response(False, "Room not found", None, 404)

            message = "Room updated successfully."
            status_code = 200

        ## `room_status` is excluded here and assigned separately below, so the
        ## normalised value wins over the raw payload.
        FIELDS = ("room_number", "room_type_id", "floor_number", "view", "notes", "is_active", "is_deleted")
        for field in FIELDS:
            if field in data:
                setattr(room, field, data[field])

        if room_status is not None:
            room.room_status = room_status

        if room.is_deleted:
            message = "Room deleted successfully."

        self.db.commit()
        self.db.refresh(room)
        return service_response(True, message, None, status_code)


    # ---------------------------------------------------------------
    # ENUM HELPERS
    # ---------------------------------------------------------------

    def _valid_room_statuses(self) -> tuple[str, ...]:
        """Allowed room statuses, read once per instance from the enum tables."""
        if self._room_status_cache is None:
            self._room_status_cache = self._load_room_statuses()
        return self._room_status_cache

    def _load_room_statuses(self) -> tuple[str, ...]:
        """`enum_options` keys for the room_status enum definition.

        NOTE the two sources disagree today: enum_seeder defines four options
        (available, cleaning, maintenance, out_of_service) while
        room_schema.UpsertRoomSchema still accepts six, adding `reserved` and
        `occupied`. CORE_ROOM_STATUSES is the union of both, so neither source
        can reject a value the other allows. Reconcile them and drop the
        redundant entries from CORE_ROOM_STATUSES.
        """
        try:
            definition = (
                self.db.query(EnumDefinition)
                .filter(
                    EnumDefinition.enum_key == ROOM_STATUS_ENUM_KEY,
                    EnumDefinition.is_deleted == False,
                )
                .first()
            )

            keys = [
                str(option.option_key).strip().lower()
                for option in (definition.options if definition else [])
                if option.is_deleted == False and option.is_active
            ]
        except Exception:
            ## Never let a bad enum table stop a room being saved: fall back to
            ## the core statuses and log loudly.
            logger.exception(
                "RoomService: could not read '%s' options. Falling back to %s.",
                ROOM_STATUS_ENUM_KEY, list(CORE_ROOM_STATUSES),
            )
            keys = []

        ## Union, not replacement, so deactivating an option in the admin UI
        ## cannot block saving a room.
        return tuple(dict.fromkeys([*keys, *CORE_ROOM_STATUSES]))

    def _normalise_room_status(self, room_status) -> str | None:
        """Bare value for the String column, or None when not an allowed option."""
        if room_status is None:
            return None

        text = str(getattr(room_status, "value", room_status)).strip().lower()
        if not text:
            return None

        return text if text in self._valid_room_statuses() else None