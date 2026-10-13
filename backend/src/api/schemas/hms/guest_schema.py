from datetime import date
from marshmallow import fields, validate
from src.api.schemas.common.id_schema import id_schema_factory
from src.api.schemas.common.pagination_schema import PaginationSchema
from src.api.schemas.fields.text import text_field
from src.api.schemas.mixins.email_mixin import EmailFieldMixin
from src.api.schemas.mixins.name_mixin import NameFieldsMixin
from src.api.schemas.mixins.phone_mixin import PhoneNumberFieldMixin


class GetAllGuestsSchema(PaginationSchema):
    pass

GetGuestByIdSchema = id_schema_factory("id", "Guest Id")

UpsertGuestIdSchema = id_schema_factory("id","Guest Id", min_value=0)

class UpsertGuestSchema(UpsertGuestIdSchema, NameFieldsMixin, EmailFieldMixin):
    """
    Fields are named to match the Guest model, not to be pretty.

    This schema used to inherit PhoneNumberFieldMixin (which declares `phone`)
    and to declare `country` / `city` / `nationality` as free text. The model
    has none of those: it stores `phone_number`, and stores location as
    `country_id` / `state_id` / `city_id` / `nationality_id` foreign keys, with
    `country` and `nationality` reserved for the relationships.

    Marshmallow's load() returns only the declared fields, so every one of
    GuestService.REQUIRED_FIELDS was stripped before the service ever saw it,
    and POST /guest/upsert failed with "Field phone_number is required" for
    every payload. Because reservation_service.create_reservation_upsert_guest
    calls upsert_guest internally, that took the booking flow down with it --
    no reservation could be created through the API at all. The seeded guests
    and reservations were written straight to the models by their seeders,
    which is why the screens looked populated.

    The Angular form, the guest seeder and GuestService all already spoke the
    model contract. The schema was the only outlier.
    """
    gender = fields.String(
        required=True,
        ## Allowed values are NOT listed here. They come from the `gender`
        ## enum definition (enum_seeder.py), validated in guest_service, so an
        ## admin adding an option does not also need a backend deploy. A
        ## hardcoded OneOf silently rejects the new option at this layer.
        validate=validate.Length(
            min=1, max=50, error="Gender is required"
        ),
        error_messages={
            "required": "Gender is required",
        }
    )
    date_of_birth = fields.Date(
        required=True,
        ## Validates that the date is between Year 1900 and Today
        validate=validate.Range(
            min=date(1900, 1, 1),
            max=date.today(),
            error="Date of birth cannot be in the future"
        ),
        error_messages={
            "required": "Date of Birth is required",
            "invalid": "Please provide a valid date format (YYYY-MM-DD)"
        }
    )
    address = text_field(
        max_len=255,
        min_len=0,
        regex=None,
        required=False,
        allow_none=True,
        label="Address"
    )
    # Location is stored as foreign keys, matching the model and the Angular
    # form. GuestService.REQUIRED_FIELDS treats all four as mandatory.
    phone_number = fields.String(
        required=True,
        validate=validate.Length(
            min=1, max=20, error="Phone number must be between 1 and 20 characters"
        ),
        error_messages={"required": "Phone number is required"},
    )
    country_id = fields.Int(
        required=True,
        allow_none=False,
        validate=validate.Range(
            min=1, error="Country must be greater than or equal to 1"
        ),
        error_messages={
            "required": "Country is required.",
            "null": "Country cannot be null.",
            "invalid": "Invalid Country.",
        },
    )
    state_id = fields.Int(
        required=True,
        allow_none=False,
        validate=validate.Range(
            min=1, error="State must be greater than or equal to 1"
        ),
        error_messages={
            "required": "State is required.",
            "null": "State cannot be null.",
            "invalid": "Invalid State.",
        },
    )
    city_id = fields.Int(
        required=True,
        allow_none=False,
        validate=validate.Range(
            min=1, error="City must be greater than or equal to 1"
        ),
        error_messages={
            "required": "City is required.",
            "null": "City cannot be null.",
            "invalid": "Invalid City.",
        },
    )
    id_type = fields.String(
        required=True,
        ## Allowed values come from the `guests_id_type` enum definition
        ## (enum_seeder.py), validated in guest_service. This list used to be
        ## ["passport", "aadhar", "driving_license", "pancard"] while the seeder
        ## and the Angular form both used "pan_card", so selecting PAN Card was
        ## rejected by the API. Do not reintroduce a hardcoded list here.
        validate=validate.Length(
            min=1, max=50, error="Id type is required"
        ),
        error_messages={
            "required": "Id type is required",
        }
    )
    id_number = text_field(
        max_len=50,
        min_len=1,
        regex=r"^[A-Za-z0-9 '-]+$",
        required=True,
        allow_none=False,
        label="Id number"
    )
    nationality_id = fields.Int(
        required=True,
        allow_none=False,
        validate=validate.Range(
            min=1,
            error="Nationality must be greater than or equal to 1"
        ),
        error_messages={
            "required": "Nationality is required.",
            "null": "Nationality cannot be null.",
            "invalid": "Invalid Nationality.",
        },
    )
    vip_status = fields.Boolean(required=True)
    blacklist_status = fields.Boolean(required=True)
    notes = text_field(
        max_len=255,
        min_len=0,
        regex=None,
        required=False,
        allow_none=True,
        label="Notes"
    )
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)