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

### The tenant itself. First of everything, because 22 tables below hold a
### foreign key to it and the FK needs the target in the registry.
from .tenant_model import Tenant

## Invitation of a new tenant's first administrator. Imported beside Tenant
## because it is created in the same provisioning step (a provisioned tenant
## with no outstanding invitation is not usable by anyone).
from .tenant_invitation_model import TenantAdminInvitation

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


### Attach the timestamp / soft-delete listeners.
#
# Imported here, at the very bottom, so that ANY entry point which touches the
# models -- app.py, an alembic env, a seeder, a management command, a test --
# gets them. Registering them only from app.py made created_at a NOT NULL
# violation waiting for the first non-Flask caller.
#
# The bottom placement is what keeps this acyclic: base_events registers
# against the declarative Base, and by this line every subclass it applies to
# has been defined.
#
# event.listen dedupes on (target, identifier, fn), so app.py also importing
# this module is harmless.
from src.api.events import base_events  # noqa: E402,F401  (imported for side effect)

### Confine every ORM query to the current tenant.
#
# Same reasoning as base_events above: the listener registers against the ORM
# Session, so any entry point that imports the models -- app.py, alembic env, a
# seeder, a script -- gets tenant enforcement. No service opts in, and none can
# forget to.
from src.api.tenancy import filters  # noqa: E402,F401  (imported for side effect)