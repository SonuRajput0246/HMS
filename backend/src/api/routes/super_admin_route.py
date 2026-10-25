"""Platform (super admin) HTTP layer.

Separate blueprint, separate URL space (`/api/super-admin`), separate guard.
The split is the whole point: these views run with no tenant bound, so they
must never share a wrapper with a path that resolves one.

Route order is deliberately public-first: `/auth/login` and `/auth/verify-mfa`
are the only endpoints that accept an unauthenticated caller. Both run
mid-sign-in, so there is no session to require yet -- the second one presents
the short-lived pending token the first handed out -- and every other rule
carries `@requires_super_admin`. There is no `requires_module` here -- that decorator
resolves grants from `role_module_access`, which is per-tenant, and a platform
admin has no tenant's role. Membership in `super_admin_users` is the grant.

These routes carry neither `__required_module__` nor `__auth_only__`: those
mark a tenant-module contract this view does not take part in, so
scripts/audit_authorization.py classifies them as public rather than reporting
a platform route as an undeclared *tenant* endpoint.
"""
from flask import Blueprint, g, jsonify, request

from src.api.middlewares.super_admin_auth import requires_super_admin
from src.api.schemas.super_admin_schema import (
    CreateSuperAdminSchema,
    ListAuditLogsSchema,
    ListSuperAdminsSchema,
    ResetSuperAdminPasswordSchema,
    SuperAdminChangePasswordSchema,
    SuperAdminEnableMfaSchema,
    SuperAdminLoginSchema,
    SuperAdminStatusSchema,
    SuperAdminVerifyMfaSchema,
    UpdateSuperAdminSchema,
)
from src.api.schemas.tenant_management_schema import (
    CreateTenantSchema,
    ListTenantsSchema,
    TenantStatusSchema,
    UpdateTenantSchema,
)
from src.api.services.audit_service import AuditService
from src.api.services.common_service import CommonService
from src.api.services.super_admin_auth_service import SuperAdminAuthService
from src.api.services.super_admin_user_service import SuperAdminUserService
from src.api.services.tenant_management_service import TenantManagementService
from src.database.session import db_session

super_admin_bp = Blueprint("super_admin", __name__)


class SuperAdminRoute:
    def __init__(self, auth_service, tenant_service, common_service, audit_service, admin_service):
        self.auth_service = auth_service
        self.tenant_service = tenant_service
        self.common_service = common_service
        self.audit_service = audit_service
        self.admin_service = admin_service

    ## ----------------------------------------------------------------- auth
    def login(self):
        ## The one public view on this blueprint: it cannot require a token it
        ## is about to issue. No tenant is resolved anywhere on this path.
        payload = request.get_json() or {}
        validated_data = SuperAdminLoginSchema().load(payload)
        result, status_code = self.auth_service.login(validated_data)
        return jsonify(result), status_code

    @requires_super_admin
    def me(self):
        result, status_code = self.auth_service.me(g.current_super_admin)
        return jsonify(result), status_code

    @requires_super_admin
    def logout(self):
        ## Reaches past the request token to the row that authorises it, so a
        ## copied bearer token dies with this session.
        result, status_code = self.auth_service.logout(g.current_super_admin)
        return jsonify(result), status_code

    def verify_mfa_login(self):
        ## Public like login: the caller holds a short-lived `super_admin_mfa_pending`
        ## token, not a session, so there is no bearer token to require here.
        payload = request.get_json() or {}
        validated_data = SuperAdminVerifyMfaSchema().load(payload)
        result, status_code = self.auth_service.verify_mfa_login(validated_data)
        return jsonify(result), status_code

    @requires_super_admin
    def change_password(self):
        ## Never takes an id: the admin is whoever the token says, so this can
        ## only ever change the caller's own password.
        validated_data = SuperAdminChangePasswordSchema().load(request.get_json() or {})
        result, status_code = self.auth_service.change_password(
            g.current_super_admin, validated_data
        )
        return jsonify(result), status_code

    @requires_super_admin
    def setup_mfa(self):
        result, status_code = self.auth_service.setup_mfa(g.current_super_admin)
        return jsonify(result), status_code

    @requires_super_admin
    def enable_mfa(self):
        validated_data = SuperAdminEnableMfaSchema().load(request.get_json() or {})
        result, status_code = self.auth_service.enable_mfa(
            g.current_super_admin, validated_data
        )
        return jsonify(result), status_code

    ## ------------------------------------------------------------- dashboard
    @requires_super_admin
    def dashboard_summary(self):
        result, status_code = self.tenant_service.dashboard_summary()
        return jsonify(result), status_code

    ## ---------------------------------------------------------------- config
    @requires_super_admin
    def platform_config(self):
        ## Public origin + tenant domain, straight from `PUBLIC_BASE_URL`. It is
        ## behind the token even though the value is not secret: every other
        ## view on this blueprint is, and opening one unauthenticated rule here
        ## would buy nothing -- the panel only renders once signed in anyway.
        result, status_code = self.tenant_service.platform_config()
        return jsonify(result), status_code

    ## -------------------------------------------------------------- lookups
    @requires_super_admin
    def list_currencies(self):
        ## A platform token cannot reach the tenant-side `/api/v1/common`
        ## lookups: those run through `authenticate()`, which needs a tenant
        ## `user_id` a platform token does not carry. These two endpoints expose
        ## the same data through the platform guard so the tenant form's
        ## currency/timezone pickers can be populated.
        result, status_code = self.common_service.get_all_currencies_list({})
        return jsonify(result), status_code

    @requires_super_admin
    def list_timezones(self):
        result, status_code = self.common_service.get_all_timezones_list({})
        return jsonify(result), status_code

    ## -------------------------------------------------------------- tenants
    @requires_super_admin
    def list_tenants(self):
        ## GET with query parameters. The tenant-side lists are POST bodies,
        ## but this one is a plain read that the panel's filters address
        ## directly, and a 404 here means "no such tab", not "no such row".
        validated_data = ListTenantsSchema().load(request.args.to_dict())
        result, status_code = self.tenant_service.get_tenants(validated_data)
        return jsonify(result), status_code

    @requires_super_admin
    def create_tenant(self):
        validated_data = CreateTenantSchema().load(request.get_json() or {})
        result, status_code = self.tenant_service.create_tenant(
            validated_data, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def get_tenant(self, tenant_id):
        result, status_code = self.tenant_service.get_tenant_by_id(tenant_id)
        return jsonify(result), status_code

    @requires_super_admin
    def update_tenant(self, tenant_id):
        validated_data = UpdateTenantSchema().load(request.get_json() or {})
        result, status_code = self.tenant_service.update_tenant(
            tenant_id, validated_data, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def set_tenant_status(self, tenant_id):
        validated_data = TenantStatusSchema().load(request.get_json() or {})
        result, status_code = self.tenant_service.set_tenant_status(
            tenant_id, validated_data["is_active"], g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def archive_tenant(self, tenant_id):
        result, status_code = self.tenant_service.archive_tenant(
            tenant_id, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def restore_tenant(self, tenant_id):
        result, status_code = self.tenant_service.restore_tenant(
            tenant_id, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def resend_admin_invitation(self, tenant_id):
        ## No body: the recipient's details come from the invitation already
        ## on record (there is no admin account yet to ask), so the only
        ## thing this call can add is the operator's decision to re-send.
        result, status_code = self.tenant_service.resend_admin_invitation(
            tenant_id, g.current_super_admin
        )
        return jsonify(result), status_code

    ## --------------------------------------------------------------- admins
    @requires_super_admin
    def list_admins(self):
        validated_data = ListSuperAdminsSchema().load(request.args.to_dict())
        result, status_code = self.admin_service.get_admins(validated_data)
        return jsonify(result), status_code

    @requires_super_admin
    def create_admin(self):
        validated_data = CreateSuperAdminSchema().load(request.get_json() or {})
        result, status_code = self.admin_service.create_admin(
            validated_data, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def get_admin(self, admin_id):
        result, status_code = self.admin_service.get_admin_by_id(admin_id)
        return jsonify(result), status_code

    @requires_super_admin
    def update_admin(self, admin_id):
        validated_data = UpdateSuperAdminSchema().load(request.get_json() or {})
        result, status_code = self.admin_service.update_admin(
            admin_id, validated_data, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def set_admin_status(self, admin_id):
        validated_data = SuperAdminStatusSchema().load(request.get_json() or {})
        result, status_code = self.admin_service.set_admin_status(
            admin_id, validated_data["is_active"], g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def reset_admin_password(self, admin_id):
        validated_data = ResetSuperAdminPasswordSchema().load(request.get_json() or {})
        result, status_code = self.admin_service.reset_admin_password(
            admin_id, validated_data, g.current_super_admin
        )
        return jsonify(result), status_code

    @requires_super_admin
    def reset_admin_mfa(self, admin_id):
        ## The second half of recovery: an administrator who lost their
        ## authenticator cannot sign in at all while MFA is compulsory, and a
        ## password reset alone leaves them still asked for a code they cannot
        ## produce. No body -- there is nothing to supply that the caller would
        ## not also be able to forge.
        result, status_code = self.admin_service.reset_admin_mfa(
            admin_id, g.current_super_admin
        )
        return jsonify(result), status_code

    ## ---------------------------------------------------------------- audit
    @requires_super_admin
    def list_audit_logs(self):
        ## The reader for the trail `tenant_management_service` and
        ## `super_admin_user_service` write. Global, like its writers.
        validated_data = ListAuditLogsSchema().load(request.args.to_dict())
        result, status_code = self.audit_service.get_logs(validated_data)
        return jsonify(result), status_code


## Instantiate services, then wrap their handlers in the platform guard.
super_admin_auth_service = SuperAdminAuthService(db=db_session)
tenant_management_service = TenantManagementService(db=db_session)
common_service = CommonService(db=db_session)
audit_service = AuditService(db=db_session)
super_admin_user_service = SuperAdminUserService(db=db_session)
super_admin_route = SuperAdminRoute(
    auth_service=super_admin_auth_service,
    tenant_service=tenant_management_service,
    common_service=common_service,
    audit_service=audit_service,
    admin_service=super_admin_user_service,
)

## Public auth. `verify-mfa` is public for the same reason login is: the caller
## presents a short-lived pending token, not a session.
super_admin_bp.add_url_rule("/auth/login", view_func=super_admin_route.login, methods=["POST"])
super_admin_bp.add_url_rule(
    "/auth/verify-mfa", view_func=super_admin_route.verify_mfa_login, methods=["POST"]
)

## Everything below requires a platform token.
super_admin_bp.add_url_rule("/auth/me", view_func=super_admin_route.me, methods=["GET"])
super_admin_bp.add_url_rule("/auth/logout", view_func=super_admin_route.logout, methods=["POST"])
super_admin_bp.add_url_rule(
    "/auth/change-password", view_func=super_admin_route.change_password, methods=["POST"]
)
super_admin_bp.add_url_rule("/auth/mfa/setup", view_func=super_admin_route.setup_mfa, methods=["POST"])
super_admin_bp.add_url_rule("/auth/mfa/enable", view_func=super_admin_route.enable_mfa, methods=["POST"])

super_admin_bp.add_url_rule(
    "/dashboard/summary", view_func=super_admin_route.dashboard_summary, methods=["GET"]
)

super_admin_bp.add_url_rule(
    "/config", view_func=super_admin_route.platform_config, methods=["GET"]
)

## Form lookups the tenant screens need. Global reference data (currencies,
## the IANA zones), so no tenant is resolved for either.
super_admin_bp.add_url_rule(
    "/lookups/currencies", view_func=super_admin_route.list_currencies, methods=["GET"]
)
super_admin_bp.add_url_rule(
    "/lookups/timezones", view_func=super_admin_route.list_timezones, methods=["GET"]
)

## Two rules on /tenants, distinguished by method: read vs register.
super_admin_bp.add_url_rule("/tenants", view_func=super_admin_route.list_tenants, methods=["GET"])
super_admin_bp.add_url_rule("/tenants", view_func=super_admin_route.create_tenant, methods=["POST"])
super_admin_bp.add_url_rule(
    "/tenants/<int:tenant_id>", view_func=super_admin_route.get_tenant, methods=["GET"]
)
super_admin_bp.add_url_rule(
    "/tenants/<int:tenant_id>", view_func=super_admin_route.update_tenant, methods=["PATCH"]
)
super_admin_bp.add_url_rule(
    "/tenants/<int:tenant_id>/status", view_func=super_admin_route.set_tenant_status, methods=["PATCH"]
)
super_admin_bp.add_url_rule(
    "/tenants/<int:tenant_id>/archive", view_func=super_admin_route.archive_tenant, methods=["POST"]
)
super_admin_bp.add_url_rule(
    "/tenants/<int:tenant_id>/restore", view_func=super_admin_route.restore_tenant, methods=["POST"]
)
## Re-issue + re-email the first administrator's invitation. POST, because it
## changes state (the previous link dies); it lives under its tenant like the
## other tenant sub-rules.
super_admin_bp.add_url_rule(
    "/tenants/<int:tenant_id>/admin-invitation/resend",
    view_func=super_admin_route.resend_admin_invitation,
    methods=["POST"],
)

## Platform operators. `admins` is read vs register by method, like `/tenants`.
super_admin_bp.add_url_rule("/admins", view_func=super_admin_route.list_admins, methods=["GET"])
super_admin_bp.add_url_rule("/admins", view_func=super_admin_route.create_admin, methods=["POST"])
super_admin_bp.add_url_rule("/admins/<int:admin_id>", view_func=super_admin_route.get_admin, methods=["GET"])
super_admin_bp.add_url_rule(
    "/admins/<int:admin_id>", view_func=super_admin_route.update_admin, methods=["PATCH"]
)
super_admin_bp.add_url_rule(
    "/admins/<int:admin_id>/status", view_func=super_admin_route.set_admin_status, methods=["PATCH"]
)
super_admin_bp.add_url_rule(
    "/admins/<int:admin_id>/reset-password",
    view_func=super_admin_route.reset_admin_password,
    methods=["POST"],
)
super_admin_bp.add_url_rule(
    "/admins/<int:admin_id>/reset-mfa",
    view_func=super_admin_route.reset_admin_mfa,
    methods=["POST"],
)

## The audit trail reader. Global, newest-first, optionally filtered.
super_admin_bp.add_url_rule(
    "/audit-logs", view_func=super_admin_route.list_audit_logs, methods=["GET"]
)
