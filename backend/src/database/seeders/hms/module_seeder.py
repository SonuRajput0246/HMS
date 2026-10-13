from sqlalchemy import select
from src.database.session import db_session
from src.api.models.common.module_model import Module
from datetime import datetime, timezone

modules_data = [
    {
        "id": 1,
        "module_name": "DASHBOARD",
        "module_display_name": "Dashboard",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "dashboard",
        "display_order_no": 1,
        "icon": "dashboard.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"}
        ]
    },
    {
        "id": 2,
        "module_name": "USER_MANAGEMENT",
        "module_display_name": "User Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "users",
        "display_order_no": 2,
        "icon": "user.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add User", "value": False, "operation_key": "Create"},
            {"key": "Edit User", "value": False, "operation_key": "Edit"},
            {"key": "Delete User", "value": False, "operation_key": "Delete"}
        ]
    },
    {
        "id": 3,
        "module_name": "ROOM",
        "module_display_name": "Room Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "rooms",
        "display_order_no": 3,
        "icon": "room.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Room", "value": False, "operation_key": "Create"},
            {"key": "Edit Room", "value": False, "operation_key": "Edit"},
            {"key": "Delete Room", "value": False, "operation_key": "Delete"}
        ]
    },
    {
        "id": 4,
        "module_name": "RESERVATIONS",
        "module_display_name": "Reservation Management",
        "menu_parent_code": 0,
        "has_child_menu": True,
        "route_path": "reservations",
        "display_order_no": 4,
        "icon": "reservation.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Reservation", "value": False, "operation_key": "Create"},
            {"key": "Edit Reservation", "value": False, "operation_key": "Edit"},
            {"key": "Delete Reservation", "value": False, "operation_key": "Delete"}
        ]
    },
    {
        "id": 5,
        "module_name": "GUEST",
        "module_display_name": "Guest Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "guests",
        "display_order_no": 5,
        "icon": "guest.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Guest", "value": False, "operation_key": "Create"},
            {"key": "Edit Guest", "value": False, "operation_key": "Edit"},
            {"key": "Delete Guest", "value": False, "operation_key": "Delete"}
        ]
    },
    {
        "id": 6,
        "module_name": "FOLIO",
        "module_display_name": "Folio & Billing",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "folio",
        "display_order_no": 6,
        "icon": "folio.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Charge", "value": False, "operation_key": "Create"},
            {"key": "Process Payment", "value": False, "operation_key": "Payment"}
        ]
    },
    {
        "id": 7,
        "module_name": "HOUSEKEEPING",
        "module_display_name": "Housekeeping",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "housekeeping",
        "display_order_no": 7,
        "icon": "cleaning.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Update Status", "value": False, "operation_key": "Edit"}
        ]
    },
    {
        "id": 8,
        "module_name": "INVENTORY_MANAGEMENT",
        "module_display_name": "Inventory Management",
        "menu_parent_code": 0,
        "has_child_menu": True,
        "route_path": "inventory",
        "display_order_no": 8,
        "icon": "inventory.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"}
        ]
    },
    {
        "id": 9,
        "module_name": "INVENTORY_CATEGORY",
        "module_display_name": "Inventory Categories",
        "menu_parent_code": 8,
        "has_child_menu": False,
        "route_path": "inventory/categories",
        "display_order_no": 8,
        "icon": "category",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Category", "value": False, "operation_key": "Create"},
            {"key": "Edit Category", "value": False, "operation_key": "Edit"},
            {"key": "Delete Category", "value": False, "operation_key": "Delete"}
        ]
    },
    {
        "id": 10,
        "module_name": "INVENTORY_ITEM",
        "module_display_name": "Inventory Items",
        "menu_parent_code": 8,
        "has_child_menu": False,
        "route_path": "inventory/items",
        "display_order_no": 8,
        "icon": "inventory_2",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Inventory", "value": False, "operation_key": "Create"},
            {"key": "Edit Inventory", "value": False, "operation_key": "Edit"},
            {"key": "Delete Inventory", "value": False, "operation_key": "Delete"},
        ]
    },
    {
        "id": 11,
        "module_name": "ROLE",
        "module_display_name": "Role Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "roles",
        "display_order_no": 11,
        "icon": "role.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Role", "value": False, "operation_key": "Create"},
            {"key": "Edit Role", "value": False, "operation_key": "Edit"},
            {"key": "Delete Role", "value": False, "operation_key": "Delete"}
        ]
    },
    {
        "id": 12,
        "module_name": "TEMPLATE",
        "module_display_name": "Template Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "templates",
        "display_order_no": 12,
        "icon": "template.png",
        "access_json": [
            {"key": "View", "value": False, "operation_key": "View"},
            {"key": "Add Template", "value": False, "operation_key": "Create"},
            {"key": "Edit Template", "value": False, "operation_key": "Edit"},
            {"key": "Delete Template", "value": False, "operation_key": "Delete"}
        ]
    },
]


def _resolve_id(module_data):
    """The id to insert under, or None to let AUTO_INCREMENT decide.

    The declared `id` is a stable contract: the frontend's `menuId` values in
    child-routes.ts and role_seeder's permission matrix both reference these
    numbers. They used to be decorative -- never passed to the constructor --
    so the real ids came from AUTO_INCREMENT and only matched on a virgin
    database.

    If the declared id is held by a *different* module, the database has
    drifted. Fall back to AUTO_INCREMENT so seeding still completes, and warn
    loudly rather than silently producing mismatched permissions.
    """
    declared = module_data.get("id")
    if declared is None:
        return None

    occupant = db_session.execute(
        select(Module).filter(Module.id == declared)
    ).scalar_one_or_none()

    if occupant is not None and occupant.module_name != module_data["module_name"]:
        print(
            f"!!! WARNING: id {declared} is already taken by "
            f"{occupant.module_name!r}, cannot use it for "
            f"{module_data['module_name']!r}. Falling back to AUTO_INCREMENT. "
            f"Front-end menuId values will not match this database."
        )
        return None

    return declared


def seed_modules_hms():
    try:
        created = 0
        for module_data in modules_data:
            stmt = select(Module).filter_by(module_name=module_data["module_name"], is_deleted=False)
            exists = db_session.execute(stmt).scalar_one_or_none()
            if not exists:
                new_module = Module(
                    id=_resolve_id(module_data),
                    module_name=module_data["module_name"],
                    module_display_name=module_data["module_display_name"],
                    menu_parent_code=module_data["menu_parent_code"],
                    has_child_menu=module_data["has_child_menu"],
                    route_path=module_data["route_path"],
                    display_order_no=module_data["display_order_no"],
                    icon=module_data["icon"],
                    access_json=module_data["access_json"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(new_module)
                created += 1

        db_session.commit()
        print(f"--- Modules seeded successfully. ({created} created) ---")
    except Exception as e:
        db_session.rollback()
        print(f"!!! Module seeder FAILED: "
              f"{str(e).encode('ascii', 'replace').decode('ascii')[:300]}")
        raise
    finally:
        db_session.remove()


if __name__ == "__main__":
    ## This used to call seed_modules(), which does not exist -- a NameError
    ## on direct execution only, since run_base_seeders imports the real name.
    seed_modules_hms()
