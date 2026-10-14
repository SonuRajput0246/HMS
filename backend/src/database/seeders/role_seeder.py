from sqlalchemy import select
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from src.api.models.role_model import Role
from src.api.models.module_model import Module
from src.api.models.role_module_access_model import RoleModuleAccess
from datetime import datetime, timezone

# ============================================
# ROLE DEFINITIONS
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
        # Custom, per the permission matrix below
    },
    {
        "role_name": "Front Desk",
        "role_code": "FRONT_DESK",
        "description": "Front desk operations",
        "is_system": False,
        # Reservations, Guests, Folio, Room
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
        # Housekeeping module
    },
    {
        "role_name": "Guest",
        "role_code": "GUEST",
        "description": "Self-registered account with no staff access",
        "is_system": True,
        # No modules. This is the role public self-registration grants, so it
        # must exist in every hotel before anyone can sign up.
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
    },
    "STAFF": {
        "DASHBOARD": ["View"],
        "RESERVATIONS": ["View"],
        "GUEST": ["View"],
        "FOLIO": ["View"],
    },
    "HOUSEKEEPING": {
        "DASHBOARD": ["View"],
        "HOUSEKEEPING": ["View", "Edit"],
        "ROOM": ["View"],
    },
    ## Self-registered accounts get nothing. Spelled out rather than omitted so
    ## the absence of grants is a visible decision, not a missing entry someone
    ## later "fixes" by adding DASHBOARD.
    "GUEST": {},
}


## Roles that may open Reports. Kept out of ROLE_PERMISSIONS above on purpose:
## that matrix is a flat role -> module map, and Reports is a module no staff
## role should reach. Listing it here makes the grant auditable in one place.
##
## MANAGER already gets it from its explicit entry; ADMIN from its wildcard.
## SUPER_ADMIN from its wildcard. No staff role is listed, which is the point.
REPORTS_ROLES = ("MANAGER",)


def seed_roles(tenant_id: int | None = None):
    """Dynamic role seeder - assigns permissions based on existing modules.

    Seeded per hotel. The module tree it reads is global (it belongs to the
    product, not to any hotel), but the roles and the grants it creates are the
    hotel's own -- so every hotel can rename its Manager role, or grant it
    different modules, without touching anyone else's.
    """
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        # 1. Get all active modules from the database.
        ## Intentionally NOT tenant-filtered: `modules` has no tenant_id. It is
        ## the product's shared menu tree, and every hotel is offered the same
        ## one to pick permissions from.
        modules = db_session.execute(
            select(Module).where(Module.is_active == True, Module.is_deleted == False)
        ).scalars().all()

        module_map = {m.module_name: m.id for m in modules}
        print(f"Found {len(modules)} active modules")

        # 2. Create/Update Roles
        for role_def in ROLE_DEFINITIONS:
            ## Scoped to the hotel. role_code is unique per tenant, so without
            ## tenant_id here the second hotel would find the first hotel's
            ## ADMIN role, decide it already exists, and inherit it -- along
            ## with every permission grant attached to it.
            role = db_session.execute(
                select(Role).where(
                    Role.tenant_id == tenant_id,
                    Role.role_code == role_def["role_code"],
                    Role.is_deleted == False
                )
            ).scalar_one_or_none()

            if not role:
                role = Role(
                    tenant_id=tenant_id,
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
            _assign_role_permissions(role, module_map, tenant_id)

        db_session.commit()
        print("--- Roles seeded successfully. ---")

    except Exception as e:
        db_session.rollback()
        print(f"Error seeding roles: {safe_error(e)}")
        raise
    finally:
        db_session.remove()


def _assign_role_permissions(role: Role, module_map: dict, tenant_id: int):
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
    ## Filtered by tenant_id as well as role_id. `role_id` is globally unique so
    ## the tenant filter changes nothing functionally -- but this is a bulk
    ## DELETE, and naming the tenant is what makes it obvious in the query log
    ## that it cannot reach another hotel's grants.
    db_session.query(RoleModuleAccess).filter_by(
        tenant_id=tenant_id, role_id=role.id
    ).delete()

    for module_pattern, operations in perm_config.items():
        if module_pattern == "*":
            # Super Admin / Admin: all modules
            target_modules = module_map.items()
        else:
            # Specific module - check if it exists in the tree
            if module_pattern in module_map:
                target_modules = [(module_pattern, module_map[module_pattern])]
            else:
                continue  # Module doesn't exist in the tree, skip

        for module_name, module_id in target_modules:
            for operation in operations:
                access = RoleModuleAccess(
                    tenant_id=tenant_id,
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
