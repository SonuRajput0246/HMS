from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from src.api.models import Role, Module, RoleModuleAccess
from src.api.utils.responses import service_response


class AdminService:
    def __init__(self, db):
        self.db = db


    def get_roles(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = data.get("search_value")
        query = self.db.query(Role).filter(Role.is_deleted == False)
        if search_value:
            val = search_value.strip()
            query = query.filter(Role.role_name.like(f"{val}%"))

        total_records = query.count()
        roles = (
            query
            .order_by(Role.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )
        role_list = [
            {
                "id": role.id,
                "role_code": role.role_code,
                "role_name": role.role_name,
                # "module_access": role.module_access,
                "is_active": role.is_active
            }
            for role in roles
        ]
        last_page = (total_records + page_size - 1) // page_size if total_records > 0 else 1
        return {
            "status": True,
            "data": role_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200


    def get_role_by_id(self, role_id):
        role = self.db.query(Role).filter_by(is_deleted=False, id=role_id).first()
        if not role:
            return service_response(False, "Role not found", None, 404)

        ## Access used to sit in `roles.module_access` as a JSON column; it now
        ## lives in role_module_access, one row per module/operation_key pair,
        ## so it is read from that table rather than off the role.
        ##
        ## `joinedload` pulls each row's module in the same query: the payload
        ## needs the module's display_order_no and access_json for ordering and
        ## the operation labels, and lazy loading would otherwise fire one query
        ## per access row.
        access_rows = (
            self.db.query(RoleModuleAccess)
            .options(joinedload(RoleModuleAccess.module))
            .filter(
                RoleModuleAccess.role_id == role_id,
                ## Soft-deleted rows are excluded; `is_active` is reported as-is
                ## so the caller can still tell a revoked operation from a
                ## granted one.
                RoleModuleAccess.is_deleted == False,
            )
            .all()
        )

        role_data = {
            "id": role.id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            ## Flat list of {id, is_active, module_id, operation_name,
            ## operation_display_name}. `operation_name` is the generic key held
            ## in the table ('Create'), while `operation_display_name` is the
            ## module's own wording from access_json ('Add User').
            "module_access": [
                {
                    "id": access.id,
                    "is_active": access.is_active,
                    "module_id": access.module_id,
                    "operation_name": access.operation_key,
                    "operation_display_name": self._operation_display_name(
                        access.module, access.operation_key
                    ),
                }
                for access in sorted(access_rows, key=self._role_access_sort_key)
            ],
            "is_active": role.is_active,
            "is_deleted": role.is_deleted
        }
        return service_response(True, "Role fetched successfully.", role_data, 200)


    def _role_access_sort_key(self, access):
        """Menu order first, then the operation order the module declares.

        access_json lists this module's operations in its intended order
        (View, then Create/Edit/Delete), so following it keeps the response
        stable instead of relying on the order rows happen to come back in.
        """
        module = access.module
        operations = (module.access_json or []) if module else []

        operation_index = len(operations)
        for position, entry in enumerate(operations):
            if entry.get("operation_key") == access.operation_key:
                operation_index = position
                break

        return (
            module.display_order_no if module else 0,
            access.module_id,
            operation_index,
        )


    def _operation_display_name(self, module, operation_key):
        """Display label for an operation, falling back to the key itself.

        Mirrors auth_service._build_menu_access so the admin editor and the
        login menu name the same operation identically.
        """
        for entry in ((module.access_json or []) if module else []):
            if entry.get("operation_key") == operation_key:
                return entry.get("key") or operation_key
        return operation_key


    def upsert_role(self, data):
        """Create (id=0), update (id>0), or soft-delete (is_deleted=True)."""
        ## `.get` rather than `data[...]`: the delete path carries only the id and
        ## the flag, so bracket access raised KeyError and surfaced as a 500.
        role_id = data.get('id', 0)
        role_code = data.get('role_code')
        is_deleted_op = data.get('is_deleted') is True

        ## ---------- CREATE ----------
        if role_id == 0:
            if is_deleted_op:
                return service_response(
                    False, "Cannot delete a role that does not exist.", None, 400
                )

            ## Rejects absent/None only. `not data.get(field)` used to treat the
            ## legitimate value `is_active=False` as a missing field and 400'd it.
            REQUIRED_FIELDS = ("role_code", "role_name", "is_active")
            for field in REQUIRED_FIELDS:
                if data.get(field) is None:
                    return service_response(
                        False, f"Field '{field}' is required.", None, 400
                    )

            ## `role_code` is `unique=True` on the model, so it is the sole
            ## identity of a role. The previous composite code+name lookup let a
            ## duplicate code through whenever the name differed, which the DB
            ## then rejected as an unhandled IntegrityError (500).
            if self._role_code_taken(role_code, role_id):
                return service_response(
                    False, "Role with this code already exists.", None, 409
                )

            role = Role()
            self.db.add(role)
            message = "Role created successfully."
            status_code = 201
        ## ---------- UPDATE / DELETE ----------
        else:
            role = self.db.query(Role).filter_by(is_deleted=False, id=role_id).first()
            if not role:
                return service_response(False, "Role not found", None, 404)

            ## Re-check uniqueness only when a new code is actually supplied,
            ## so a partial update is not blocked by the row's own current code.
            if not is_deleted_op and role_code is not None and role_code != role.role_code:
                if self._role_code_taken(role_code, role_id):
                    return service_response(
                        False, "Role with this code already exists.", None, 409
                    )

            message = "Role updated successfully."
            status_code = 200

        ## `role_code` was missing from this tuple: it was validated above but
        ## never written, so every insert failed on the NOT NULL constraint and
        ## every attempt to edit a code was silently discarded.
        FIELDS = ("role_code", "role_name", "is_active", "is_deleted")
        for field in FIELDS:
            if field in data:
                setattr(role, field, data[field])

        if role.is_deleted:
            message = "Role deleted successfully."

        self.db.commit()
        self.db.refresh(role)
        return service_response(True, message, None, status_code)


    def _role_code_taken(self, role_code, exclude_role_id):
        """True when another live role already owns `role_code`."""
        return self.db.query(Role).filter(
            Role.is_deleted == False,
            Role.role_code == role_code,
            Role.id != exclude_role_id
        ).first() is not None


    def get_all_modules(self):
        modules = self.db.query(Module).filter(Module.is_deleted == False).all()
        modules_list = [
            {
                "id": module.id,
                "module_name": module.module_name,
                "module_display_name": module.module_display_name,
                "menu_parent_code": module.menu_parent_code,
                "has_child_menu": module.has_child_menu,
                "route_path": module.route_path,
                "display_order_no": module.display_order_no,
                "icon": module.icon,
                "access_json": module.access_json,
                "is_active": module.is_active
            }
            for module in modules
        ]
        return {
            "status": True,
            "data": modules_list
        }, 200

    def update_role_access(self, data):
        """Replace a role's whole access set with the supplied payload.

        The editor builds the payload from the full module list, so it is
        treated as the complete set: anything absent is revoked.

        Revocation is a hard delete rather than a soft delete. `uq_role_module_op`
        covers (role_id, module_id, operation_key) only, so a soft-deleted row
        would permanently block that same operation from ever being granted
        again on this role.
        """
        role_id = data.get("role_id")
        role = self.db.query(Role).filter_by(id=role_id, is_deleted=False).first()
        if not role:
            return service_response(False, "Role not found", None, 404)

        if "role_module_access" not in data:
            return service_response(
                False, "Field 'role_module_access' is required.", None, 400
            )

        access_items = data["role_module_access"]
        if not isinstance(access_items, list):
            return service_response(
                False, "Field 'role_module_access' must be a list.", None, 400
            )

        ## ---------- VALIDATE THE WHOLE PAYLOAD BEFORE WRITING ----------
        requested = []
        module_ids = set()

        for index, item in enumerate(access_items):
            if not isinstance(item, dict):
                return service_response(
                    False, f"Access item at index {index} must be an object.", None, 400
                )

            module_id = item.get("module_id")
            ## The client sends the generic key under `operation_name`, while the
            ## column is `operation_key`. `operation_display_name` is the
            ## module's own wording from access_json and is deliberately ignored:
            ## the row stores only the key, and that label is re-derived on read.
            operation_key = item.get("operation_name")
            if module_id is None or not operation_key:
                return service_response(
                    False,
                    f"Access item at index {index} requires 'module_id' "
                    "and 'operation_name'.",
                    None, 400,
                )

            ## An explicit is_active=false is a revocation: it is left out of the
            ## resulting set instead of being stored as an inactive row, since
            ## the next save replaces the set wholesale either way.
            if item.get("is_active") is False:
                continue

            requested.append((module_id, operation_key))
            module_ids.add(module_id)

        ## One lookup for every module involved, rather than one per item.
        modules = {}
        if module_ids:
            modules = {
                module.id: module
                for module in self.db.query(Module)
                .filter(Module.id.in_(module_ids), Module.is_deleted == False)
                .all()
            }

        ## Dict keyed by (module_id, operation_key): the editor emits a
        ## hardcoded 'View' per enabled module *and* pushes the View entry from
        ## access_json again when a grant already exists, so the same triple can
        ## arrive twice. `uq_role_module_op` rejects duplicates, so collapsing
        ## them here keeps the insert set valid. Last write wins, one row each.
        desired = {}
        for module_id, operation_key in requested:
            module = modules.get(module_id)
            if module is None:
                return service_response(
                    False, f"Module {module_id} not found.", None, 404
                )

            ## Reject operations the module never declared: such a row would
            ## never be matched by any screen and would only grant a meaningless
            ## privilege. All 27 seeded modules declare 'View', which the editor
            ## sends unconditionally.
            if operation_key not in self._declared_operations(module):
                return service_response(
                    False,
                    f"Operation '{operation_key}' is not supported by module "
                    f"'{module.module_display_name}'.",
                    None, 400,
                )

            desired[(module_id, operation_key)] = True

        ## ---------- WRITE ----------
        ## created_at/updated_at are NOT NULL with no column default, so they
        ## have to be supplied here the way the seeder does.
        now = datetime.now(timezone.utc)

        try:
            self.db.query(RoleModuleAccess).filter(
                RoleModuleAccess.role_id == role_id
            ).delete(synchronize_session=False)

            for module_id, operation_key in desired:
                self.db.add(RoleModuleAccess(
                    role_id=role_id,
                    module_id=module_id,
                    operation_key=operation_key,
                    is_active=True,
                    is_deleted=False,
                    created_at=now,
                    updated_at=now,
                    deleted_at=None,
                ))

            self.db.commit()
        except SQLAlchemyError:
            ## Leaves the role's previous access intact rather than committing a
            ## half-applied set.
            self.db.rollback()
            return service_response(
                False, "Failed to update role access.", None, 500
            )

        return service_response(
            True,
            "Role Access updated successfully.",
            {"granted_count": len(desired)},
            200,
        )


    def _declared_operations(self, module):
        """Operation keys a module supports, taken from its access_json."""
        return {
            entry.get("operation_key")
            for entry in (module.access_json or [])
            if entry.get("operation_key")
        }