from flask import Blueprint, jsonify, request

from src.api.middlewares.platform_auth import platform_required
from src.api.schemas.platform_schema import (
    CreateTenantSchema,
    PlatformLoginSchema,
    ResetTenantAdminPasswordSchema,
    SuspendTenantSchema,
)
from src.api.services.platform_service import PlatformService
from src.database.session import db_session

platform_bp = Blueprint("platform", __name__)


class PlatformRoute:
    def __init__(self, platform_service):
        self.platform_service = platform_service


    def login(self):
        data = PlatformLoginSchema().load(request.get_json() or {})
        result, status_code = self.platform_service.login(data)
        return jsonify(result), status_code


    def list_tenants(self):
        result, status_code = self.platform_service.list_tenants()
        return jsonify(result), status_code


    def create_tenant(self):
        data = CreateTenantSchema().load(request.get_json() or {})
        result, status_code = self.platform_service.create_tenant(data)
        return jsonify(result), status_code


    def suspend_tenant(self, tenant_id):
        data = SuspendTenantSchema().load(request.get_json() or {})
        result, status_code = self.platform_service.set_suspended(
            tenant_id, True, data["reason"]
        )
        return jsonify(result), status_code


    def reactivate_tenant(self, tenant_id):
        result, status_code = self.platform_service.set_suspended(tenant_id, False)
        return jsonify(result), status_code


    def reset_admin_password(self, tenant_id):
        data = ResetTenantAdminPasswordSchema().load(request.get_json() or {})
        result, status_code = self.platform_service.reset_admin_password(
            tenant_id, data["password"]
        )
        return jsonify(result), status_code


platform_service_instance = PlatformService(db=db_session)
platform_route = PlatformRoute(platform_service=platform_service_instance)

## Public: this is how an operator gets a platform token in the first place.
platform_bp.add_url_rule("/login", view_func=platform_route.login, methods=["POST"])

## Everything else needs a platform token. These routes are exempt from tenant
## resolution (see TENANT_EXEMPT_PREFIXES): they administer hotels, so they cannot
## themselves belong to one.
platform_bp.add_url_rule(
    "/tenants", view_func=platform_required(platform_route.list_tenants), methods=["GET"]
)
platform_bp.add_url_rule(
    "/tenants", view_func=platform_required(platform_route.create_tenant), methods=["POST"]
)
platform_bp.add_url_rule(
    "/tenants/<int:tenant_id>/suspend",
    view_func=platform_required(platform_route.suspend_tenant),
    methods=["POST"],
)
platform_bp.add_url_rule(
    "/tenants/<int:tenant_id>/reactivate",
    view_func=platform_required(platform_route.reactivate_tenant),
    methods=["POST"],
)
platform_bp.add_url_rule(
    "/tenants/<int:tenant_id>/reset-admin-password",
    view_func=platform_required(platform_route.reset_admin_password),
    methods=["POST"],
)
