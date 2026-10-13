from sqlalchemy import select
from src.database.session import db_session
from src.api.models.common.role_model import Role
from src.api.models.common.module_model import Module
from src.api.models.common.role_module_access_model import RoleModuleAccess
from datetime import datetime, timezone

# ============================================
# ROLE DEFINITIONS (Shared across instances)
# ============================================
ROLE_DEFINITIONS = [
    {
        "role_name": "Super Admin",
        "role_code": "SUPER_ADMIN",
        "description": "Full system access",
        "is_system": True,
        # Gets ALL modules automatically
    },
    {
        "role_name": "Admin",
        "role_code": "ADMIN",
        "description": "Administrative access",
        "is_system": True,
        # Gets most modules except super-admin only
    },
    {
        "role_name": "Manager",
        "role_code": "MANAGER",
        "description": "Management access",
        "is_system": False,
        # Custom per instance via module patterns
    },
    {
        "role_name": "Front Desk",
        "role_code": "FRONT_DESK",
        "description": "Front desk operations",
        "is_system": False,
        # HMS: Reservations, Guests, Folio | CMS: Orders, Tables, POS
    },
    {
        "role_name": "Staff",
        "role_code": "STAFF",
        "description": "Basic staff access",
        "is_system": False,
        # Limited view access
    },
    {
        "role_name": "Housekeeping",
        "role_code": "HOUSEKEEPING",
        "description": "Housekeeping staff",
        "is_system": False,
        # HMS only: Housekeeping module
    },
    {
        "role_name": "Kitchen Staff",
        "role_code": "KITCHEN_STAFF",
        "description": "Kitchen operations",
        "is_system": False,
        # CMS only: KDS, Orders (prep)
    },
    {
        "role_name": "Waiter",
        "role_code": "WAITER",
        "description": "Floor service staff",
        "is_system": False,
        # CMS only: Tables, Orders (serve), POS
    },
]

# ============================================
# PERMISSION MATRIX BY MODULE PATTERN
# ============================================
# Maps role_code -> list of module_name patterns + operations
ROLE_PERMISSIONS = {
    "SUPER_ADMIN": {
        # Export included: it is the operation that pulls bulk business data
        # out, and a super admin with no way to export is a support ticket.
        "*": ["Create", "Edit", "Delete", "View", "Export"]  # All modules, all ops
    },
    "ADMIN": {
        "*": ["Create", "Edit", "Delete", "View"],
        ## Plus REPORTS/Export -- see REPORTS_ROLES. A wildcard cannot express
        ## "everything except Export on reports", and Export is the operation
        ## that pulls bulk business data out of the system.
        "REPORTS": ["Export"],
    },
    "MANAGER": {
        "DASHBOARD": ["View"],
        "USER_MANAGEMENT": ["View"],
        "ROLE": ["View"],
        "TEMPLATE": ["View"],
        "INVENTORY_MANAGEMENT": ["View"],
        "INVENTORY_CATEGORY": ["Create", "Edit", "View"],
        "INVENTORY_ITEM": ["Create", "Edit", "View"],
    },
    "FRONT_DESK": {
        "DASHBOARD": ["View"],
        # HMS modules (will only apply if module exists)
        "RESERVATIONS": ["Create", "Edit", "View"],
        "GUEST": ["Create", "Edit", "View"],
        "FOLIO": ["View", "Create", "Payment"],
        "ROOM": ["View"],
        # CMS modules (will only apply if module exists)
        "TABLE": ["View", "Edit"],
        "ORDER": ["Create", "Edit", "View", "Void"],
        "CUSTOMER": ["Create", "Edit", "View"],
        "POS": ["View", "Payment", "Split"],
        "KDS": ["View"],
    },
    "STAFF": {
        "DASHBOARD": ["View"],
        # HMS
        "RESERVATIONS": ["View"],
        "GUEST": ["View"],
        "FOLIO": ["View"],
        # CMS
        "TABLE": ["View"],
        "ORDER": ["View"],
        "CUSTOMER": ["View"],
        "POS": ["View"],
    },
    "HOUSEKEEPING": {
        "DASHBOARD": ["View"],
        "HOUSEKEEPING": ["View", "Edit"],
        "ROOM": ["View"],
    },
    "KITCHEN_STAFF": {
        "DASHBOARD": ["View"],
        "KDS": ["View", "Edit"],
        "ORDER": ["View", "Edit"],  # Update prep status
        "INVENTORY_ITEM": ["View"],  # Check stock
    },
    "WAITER": {
        "DASHBOARD": ["View"],
        "TABLE": ["View", "Edit"],
        "ORDER": ["Create", "Edit", "View", "Void"],
        "CUSTOMER": ["View"],
        "POS": ["View", "Payment"],
        "KDS": ["View"],
    },
}


## Roles that may open Reports. Kept out of ROLE_PERMISSIONS above on purpose:
## that matrix is a flat role -> module map, and Reports is a module no staff
## role should reach. Listing it here makes the grant auditable in one place.
##
## MANAGER already gets it from its explicit entry; ADMIN from its wildcard.
## SUPER_ADMIN from its wildcard. No staff role is listed, which is the point.
REPORTS_ROLES = ("MANAGER",)


def seed_roles():
    """Dynamic role seeder - assigns permissions based on existing modules"""
    try:
        # 1. Get all active modules from DATABASE (instance-specific)
        modules = db_session.execute(
            select(Module).where(Module.is_active == True, Module.is_deleted == False)
        ).scalars().all()

        module_map = {m.module_name: m.id for m in modules}
        print(f"Found {len(modules)} active modules in this instance")

        # 2. Create/Update Roles
        for role_def in ROLE_DEFINITIONS:
            role = db_session.execute(
                select(Role).where(Role.role_code == role_def["role_code"], Role.is_deleted == False)
            ).scalar_one_or_none()

            if not role:
                role = Role(
                    role_name=role_def["role_name"],
                    role_code=role_def["role_code"],
                    description=role_def["description"],
                    is_system=role_def["is_system"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(role)
                db_session.flush()  # Get ID
                print(f"  Created role: {role.role_name}")
            else:
                role.role_name = role_def["role_name"]
                role.description = role_def["description"]
                role.updated_at = datetime.now(timezone.utc)
                print(f"  Updated role: {role.role_name}")

            # 3. Assign permissions based on modules that EXIST in this DB
            _assign_role_permissions(role, module_map)

        db_session.commit()
        print("--- Roles seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print(f"Error seeding roles: {e}")
        raise
    finally:
        db_session.remove()


def _assign_role_permissions(role: Role, module_map: dict):
    """Assign module permissions to role based on what modules exist"""

    # Get permission config for this role
    perm_config = ROLE_PERMISSIONS.get(role.role_code, {})

    ## Reports is granted from REPORTS_ROLES rather than ROLE_PERMISSIONS, so
    ## the set of roles that can open it is auditable in one place. The lookup
    ## returns a fresh dict because ROLE_PERMISSIONS entries are module-level
    ## objects and mutating one would leak across roles on a re-seed.
    perm_config = dict(perm_config)
    if role.role_code in REPORTS_ROLES:
        perm_config["REPORTS"] = ["View", "Export"]

    # Clear existing permissions (for idempotent seeding)
    db_session.query(RoleModuleAccess).filter_by(role_id=role.id).delete()

    for module_pattern, operations in perm_config.items():
        if module_pattern == "*":
            # Super Admin / Admin: all modules
            target_modules = module_map.items()
        else:
            # Specific module - check if it exists in THIS instance
            if module_pattern in module_map:
                target_modules = [(module_pattern, module_map[module_pattern])]
            else:
                continue  # Module doesn't exist in this instance, skip

        for module_name, module_id in target_modules:
            for operation in operations:
                access = RoleModuleAccess(
                    role_id=role.id,
                    module_id=module_id,
                    operation_key=operation,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(access)

    db_session.flush()


if __name__ == "__main__":
    seed_roles()