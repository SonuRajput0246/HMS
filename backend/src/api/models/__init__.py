"""SQLAlchemy model registry.

Import order is load-bearing, not cosmetic: `relationship()` targets must
already be in the declarative registry when a child class body executes, so
parents are imported before their children. The CMS block below is the only
part that is load-bearing across buckets (order -> table -> recipe -> ...).

This module must import every mapped class before create_all()/alembic runs.
Any entry point that touches models -- app.py, alembic env, seeders -- imports
it and therefore gets the full registry.

Bucket layout:
  common/  shared by HMS and CMS (identity, access, inventory, reference data)
  hms/     hotel only (rooms, reservations, folio, invoicing)
  cms/     cafe only (tables, recipes, orders)
"""

### Importing all the Models
from .common.role_model import Role
from .common.user_model import User
from .common.token_model import Token
from .common.email_otp_model import EmailOTP
from .common.module_model import Module
from .common.inventory_category_model import InventoryCategory
from .common.inventory_model import Inventory
from .common.account_deletions_model import AccountDeletions
from .common.login_sliders_model import LoginSliders
from .common.inventory_units_model import InventoryUnits
from .hms.room_type_model import RoomType
from .hms.room_amenity_model import RoomAmenity
from .hms.room_type_amenity_model import RoomTypeAmenity
from .hms.room_model import Room
from .hms.room_blocks_model import RoomBlocks
from .common.prefixes_model import Prefixes
from .hms.reservation_sequence_model import ReservationSequence
from .hms.reservation_model import Reservation
from .common.country_model import Country
from .common.state_model import State
from .common.city_model import City
from .hms.guest_model import Guest
from .hms.additional_guest_model import AdditionalGuest
from .hms.reservation_primary_guest_model import ReservationPrimaryGuest
from .hms.reservation_additional_guest_model import ReservationAdditionalGuest
# from .folio_model import Folio
# from .folio_charges_model import FolioCharge
# from .invoice_model import Invoice
# from .invoice_items_model import InvoiceItem
# from .services_model import Service
from .hms.payment_model import Payment
# from .tax_config_model import TaxConfig
# from .refund_model import Refund
from .common.currency_model import Currency
from .common.system_setting_model import SystemSetting
# from .room_type_pricing_model import RoomTypePricing
from .common.template_model import Template
from .common.enum_definitions_model import EnumDefinition
from .common.enum_options_model import EnumOption
from .common.role_module_access_model import RoleModuleAccess

### CMS Models (Cafe Management System)
# NOTE: import order matters. Parents first so children's relationship()
# targets are already in the registry.
from .cms.table_zone_model import TableZone
from .cms.table_model import Table
from .cms.customer_model import Customer
from .cms.recipe_category_model import RecipeCategory
from .cms.recipe_model import Recipe
from .cms.recipe_ingredient_model import RecipeIngredient
from .common.document_sequence_model import DocumentSequence
from .cms.order_model import (
    CMSOrder,
    CMSOrderItem,
    CMSPayment,
    OrderStatusEnum,
    OrderTypeEnum,
    PaymentStatusEnum,
    PaymentMethodEnum,
)

### Attach the CMS timestamp / soft-delete listeners.
#
# Imported here, at the very bottom, so that ANY entry point which touches the
# models -- app.py, an alembic env, a seeder, a management command, a test --
# gets them. Registering them only from app.py made created_at a NOT NULL
# violation waiting for the first non-Flask caller.
#
# The bottom placement is what keeps this acyclic: cms_events imports the model
# modules directly, and by this line they are all fully resolved.
#
# event.listen dedupes on (target, identifier, fn), so app.py also importing
# this module is harmless.
from src.api.events import cms_events  # noqa: E402,F401  (imported for side effect)
