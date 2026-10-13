from sqlalchemy import select
from src.database.session import db_session
from src.api.models.common.module_model import Module
from datetime import datetime, timezone

modules_data = [{
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
    }, {
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
    }, {
        "id": 3,
        "module_name": "TABLE",
        "module_display_name": "Table Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "tables",
        "display_order_no": 3,
        "icon": "table_restaurant.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Table", "value": False, "operation_key": "Create"},
			{"key": "Edit Table", "value": False, "operation_key": "Edit"},
			{"key": "Delete Table", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 4,
        "module_name": "ORDER",
        "module_display_name": "Order Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "orders",
        "display_order_no": 4,
        "icon": "receipt_long.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Create Order", "value": False, "operation_key": "Create"},
			{"key": "Void Item", "value": False, "operation_key": "Void"},
			{"key": "Process Payment", "value": False, "operation_key": "Payment"}
        ]
    }, {
        "id": 5,
        "module_name": "CUSTOMER",
        "module_display_name": "Customer Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "customers",
        "display_order_no": 5,
        "icon": "customer.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Customer", "value": False, "operation_key": "Create"},
			{"key": "Edit Customer", "value": False, "operation_key": "Edit"},
			{"key": "Delete Customer", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 6,
        "module_name": "KDS",
        "module_display_name": "Kitchen Display (KDS)",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "kds",
        "display_order_no": 6,
        "icon": "kitchen.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Update Status", "value": False, "operation_key": "Edit"}
        ]
    }, {
        "id": 7,
        "module_name": "POS",
        "module_display_name": "POS / Billing",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "pos",
        "display_order_no": 7,
        "icon": "point_of_sale.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Process Payment", "value": False, "operation_key": "Payment"},
			{"key": "Split Bill", "value": False, "operation_key": "Split"}
        ]
    }, {
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
    }, {
        "id": 9,
        "module_name": "INVENTORY_CATEGORY",
        "module_display_name": "Inventory Category",
        "menu_parent_code": 8,
        "has_child_menu": False,
        "route_path": "inventory/categories",
        "display_order_no": 8,
        "icon": "category.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Category", "value": False, "operation_key": "Create"},
			{"key": "Edit Category", "value": False, "operation_key": "Edit"},
			{"key": "Delete Category", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 10,
        "module_name": "INVENTORY_ITEM",
        "module_display_name": "Inventory Items",
        "menu_parent_code": 8,
        "has_child_menu": False,
        "route_path": "inventory/items",
        "display_order_no": 8,
        "icon": "inventory_2.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Item", "value": False, "operation_key": "Create"},
			{"key": "Edit Item", "value": False, "operation_key": "Edit"},
			{"key": "Delete Item", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 11,
        "module_name": "RECIPE",
        "module_display_name": "Recipe Management",
        "menu_parent_code": 0,
        "has_child_menu": True,
        "route_path": "recipes",
        "display_order_no": 9,
        "icon": "menu_book.png",
        "access_json": [{"key": "View", "value": False, "operation_key": "View"}
        ]
    }, {
        "id": 12,
        "module_name": "RECIPE_ITEM",
        "module_display_name": "Recipes",
        "menu_parent_code": 11,
        "has_child_menu": False,
        "route_path": "recipes/list",
        "display_order_no": 1,
        "icon": "recipe.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Recipe", "value": False, "operation_key": "Create"},
			{"key": "Edit Recipe", "value": False, "operation_key": "Edit"},
			{"key": "Delete Recipe", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 13,
        "module_name": "RECIPE_CATEGORY",
        "module_display_name": "Recipe Categories",
        "menu_parent_code": 11,
        "has_child_menu": False,
        "route_path": "recipes/categories",
        "display_order_no": 2,
        "icon": "recipe_category.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Category", "value": False, "operation_key": "Create"},
			{"key": "Edit Category", "value": False, "operation_key": "Edit"},
			{"key": "Delete Category", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 14,
        "module_name": "ROLE",
        "module_display_name": "Role Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "roles",
        "display_order_no": 10,
        "icon": "role.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Role", "value": False, "operation_key": "Create"},
			{"key": "Edit Role", "value": False, "operation_key": "Edit"},
			{"key": "Delete Role", "value": False, "operation_key": "Delete"}
        ]
    }, {
        "id": 15,
        "module_name": "TEMPLATE",
        "module_display_name": "Template Management",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "templates",
        "display_order_no": 11,
        "icon": "template.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Add Template", "value": False, "operation_key": "Create"},
			{"key": "Edit Template", "value": False, "operation_key": "Edit"},
			{"key": "Delete Template", "value": False, "operation_key": "Delete"}
        ]
    }, {
        ## Reports reads sales figures, kitchen performance and customer data,
        ## so it needs its own module row. It previously had none: the frontend
        ## pointed /cms/reports at menuId 1 (DASHBOARD) purely so the route was
        ## reachable, which handed report data to anyone with dashboard access.
        "id": 16,
        "module_name": "REPORTS",
        "module_display_name": "Reports",
        "menu_parent_code": 0,
        "has_child_menu": False,
        "route_path": "reports",
        "display_order_no": 12,
        "icon": "menu_book.png",
        "access_json": [
			{"key": "View", "value": False, "operation_key": "View"},
			{"key": "Export", "value": False, "operation_key": "Export"}
        ]
    },
]


def _resolve_id(module_data):
    """The id to insert under, or None to let AUTO_INCREMENT decide.

    The declared `id` is a stable contract: the frontend's `menuId` values and
    role_seeder's permission matrix both reference these numbers. They used to
    be decorative -- never passed to the constructor -- so the real ids came
    from AUTO_INCREMENT and only happened to match on a virgin database.

    If the declared id is already held by a *different* module, that database
    has drifted (rows inserted out of band, a partial restore). Falling back to
    AUTO_INCREMENT keeps the seed working; the warning names the module so the
    drift is visible rather than silently producing wrong permissions.
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


def seed_modules_cms():
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
    seed_modules_cms()
