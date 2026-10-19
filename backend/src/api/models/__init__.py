"""SQLAlchemy model registry.

Every mapped class lives directly in this package -- there is no sub-bucketing.
Import the specific model you need from here.

Import order is load-bearing, not cosmetic: `relationship()` targets must
already be in the declarative registry when a child class body executes, so
parents are imported before their children.

This module must import every mapped class before create_all()/alembic runs.
Any entry point that touches models -- app.py, alembic env, seeders -- imports
it and therefore gets the full registry.
"""

### Importing all the Models
##
## Tenant first: it is the parent every tenant-scoped table points at, and
## relationship() targets must already be in the registry when a child class
## body executes.
from .tenant_model import Tenant
from .role_model import Role
from .user_model import User

## Platform identity. Global, like `tenants` itself: neither carries a
## `tenant_id`, and neither is reachable from a hotel token. `super_admin_tokens`
## is a parent-by-FK of `super_admin_users`, so it is imported after it.
from .super_admin_user_model import SuperAdminUser
from .super_admin_token_model import SuperAdminToken

## The platform activity trail. Also global -- see the docstring on the model.
from .audit_log_model import AuditLog

from .token_model import Token
from .email_otp_model import EmailOTP
from .module_model import Module
from .inventory_category_model import InventoryCategory
from .inventory_model import Inventory
from .account_deletions_model import AccountDeletions
from .login_sliders_model import LoginSliders
from .inventory_units_model import InventoryUnits
from .room_type_model import RoomType
from .room_amenity_model import RoomAmenity
from .room_type_amenity_model import RoomTypeAmenity
from .room_model import Room
from .room_blocks_model import RoomBlocks
from .prefixes_model import Prefixes
from .reservation_sequence_model import ReservationSequence
from .reservation_model import Reservation
from .country_model import Country
from .state_model import State
from .city_model import City
from .guest_model import Guest
from .additional_guest_model import AdditionalGuest
from .reservation_primary_guest_model import ReservationPrimaryGuest
from .reservation_additional_guest_model import ReservationAdditionalGuest
from .payment_model import Payment
from .currency_model import Currency
from .system_setting_model import SystemSetting
from .template_model import Template
from .enum_definitions_model import EnumDefinition
from .enum_options_model import EnumOption
from .role_module_access_model import RoleModuleAccess
