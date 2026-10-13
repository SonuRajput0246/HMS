from marshmallow import fields, validate
from src.api.schemas.base import BaseSchema
from src.api.schemas.id_schema import id_schema_factory
from src.api.schemas.fields.name import name_field

GetRoleByIdSchema = id_schema_factory("id", "Role Id")
UpsertRoleIdSchema = id_schema_factory("id", "Role Id", min_value=0, required=True)

class UpsertRoleSchema(UpsertRoleIdSchema):
    role_code = name_field("Role Code")
    role_name = name_field("Role Name")
    is_active = fields.Boolean(required=True)
    is_deleted = fields.Boolean(required=True)


## Define the schema for the items INSIDE the list first
class RoleModuleAccessItemSchema(BaseSchema):
    ## `id` is optional, and AdminService.update_role_access ignores it: the
    ## service keys the incoming set on (module_id, operation_key) and hard-
    ## deletes whatever is absent.
    ##
    ## It was required=True, so a caller had to supply a value the service
    ## never reads. On an edit round trip the Angular screen sends back the row
    ## id get-role-by-id gave it; on a *new* grant there is no row yet, so it
    ## sends a local counter++. Any other client -- a script, a test, another
    ## frontend -- that sent exactly the fields the service reads was rejected
    ## with {'id': ['Missing data for required field.']}.
    id = fields.Int(required=False, allow_none=True)
    is_active = fields.Bool(required=True)
    module_id = fields.Int(required=True)
    operation_name = fields.Str(required=True)
    operation_display_name = fields.Str(required=True)


UpdateRoleAccessRoleIdSchema = id_schema_factory("role_id", "Role Id", min_value=1, required=True)

class UpdateRoleAccessSchema(UpdateRoleAccessRoleIdSchema):
    ## Use fields.List with fields.Nested to handle the array of objects
    role_module_access = fields.List(
        fields.Nested(RoleModuleAccessItemSchema),
        required=True
    )
