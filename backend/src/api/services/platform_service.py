"""Platform administration: log in, then manage tenants from above.

Everything here runs outside any tenant. The requesting operator belongs to no
hotel, and the rows this touches are either above tenancy (`tenants`,
`platform_users`) or explicitly scoped for one operation (`reset_admin_password`
enters the tenant it is resetting).

`create_tenant` is the provisioning path from docs/multi-tenancy.md §7. It calls
`provision_tenant`, which drops and re-acquires the session per seeder -- so by
the time it returns, the session this service was holding has been closed. That
is why every value read back off a created or updated tenant is turned into a
plain dict immediately rather than kept as an ORM object.
"""
from datetime import datetime, timezone

from src.api.extensions import bcrypt
from src.api.middlewares.platform_auth import mint_platform_token
from src.api.models.platform_user_model import PlatformUser
from src.api.models.role_model import Role
from src.api.models.tenant_model import Tenant
from src.api.models.token_model import Token
from src.api.models.user_model import User
from src.api.utils.responses import service_response
from src.database.tenant_context import tenant_context


class PlatformService:

    def __init__(self, db):
        self.db = db


    ## -- authentication ----------------------------------------------------

    def login(self, data: dict):
        platform_user = (
            self.db.query(PlatformUser)
            .filter_by(is_deleted=False, email=data["email"])
            .first()
        )
        if not platform_user or not bcrypt.check_password_hash(
            platform_user.password.encode("utf-8"), data["password"].encode("utf-8")
        ):
            return service_response(False, "Invalid email or password.", None, 401)

        if not platform_user.is_active:
            return service_response(False, "Platform account is deactivated.", None, 403)

        token = mint_platform_token(platform_user)
        return service_response(
            True,
            "Login successful.",
            {"access_token": token, "platform_user": self._user_dict(platform_user)},
            200,
        )


    ## -- tenants -----------------------------------------------------------

    def list_tenants(self):
        tenants = (
            self.db.query(Tenant)
            .filter_by(is_deleted=False)
            .order_by(Tenant.id.asc())
            .all()
        )
        return service_response(
            True, "Tenants fetched.", [self._tenant_dict(t) for t in tenants], 200
        )


    def create_tenant(self, data: dict):
        ## Imported here, not at module import time: the seeders are only needed
        ## when a tenant is actually created, and importing them with the routes
        ## would pull the whole seeding graph into every boot.
        from src.database.seeders.provision_tenant import provision_tenant

        tenant = provision_tenant(
            slug=data["slug"],
            name=data["name"],
            admin_email=data["admin_email"],
            admin_password=data["admin_password"],
        )
        return service_response(
            True, "Tenant provisioned.", self._tenant_dict(tenant), 201
        )


    def set_suspended(self, tenant_id: int, suspended: bool, reason: str | None = None):
        tenant = self._tenant(tenant_id)
        if tenant is None:
            return service_response(False, "Tenant not found.", None, 404)

        tenant.is_suspended = suspended
        tenant.suspended_reason = (
            reason if suspended else None
        )
        self.db.commit()

        message = "Tenant suspended." if suspended else "Tenant reactivated."
        return service_response(True, message, self._tenant_dict(tenant), 200)


    def reset_admin_password(self, tenant_id: int, new_password: str):
        """Reset a tenant's super admin password, and end its live sessions.

        The admin lives inside the tenant, so the lookup is scoped to it. A
        platform request carries no tenant of its own, so the scope is entered
        explicitly rather than assumed from the ambient context.
        """
        tenant = self._tenant(tenant_id)
        if tenant is None:
            return service_response(False, "Tenant not found.", None, 404)

        with tenant_context(tenant.id):
            admin = (
                self.db.query(User)
                .join(Role, Role.id == User.role_id)
                .filter(
                    Role.role_code == "SUPER_ADMIN",
                    User.is_deleted == False,
                    User.is_active == True,
                )
                .order_by(User.id.asc())
                .first()
            )
            if admin is None:
                return service_response(
                    False, "This tenant has no active super admin.", None, 404
                )

            admin.password = bcrypt.generate_password_hash(new_password, 12).decode("utf-8")
            admin.last_password_update_at = datetime.now(timezone.utc)

            ## A reset that leaves the old sessions alive is cosmetic: whoever
            ## held the old password keeps the tokens it bought. Revoke them the
            ## way logout does.
            self.db.query(Token).filter(
                Token.user_id == admin.id,
                Token.is_revoked == False,
            ).update({"is_revoked": True})
            self.db.commit()

        return service_response(True, "Admin password reset.", {"tenant_id": tenant.id}, 200)


    ## -- helpers -----------------------------------------------------------

    def _tenant(self, tenant_id: int):
        return (
            self.db.query(Tenant)
            .filter_by(id=tenant_id, is_deleted=False)
            .first()
        )

    @staticmethod
    def _user_dict(platform_user) -> dict:
        return {
            "id": platform_user.id,
            "email": platform_user.email,
            "first_name": platform_user.first_name,
            "last_name": platform_user.last_name,
        }

    @staticmethod
    def _tenant_dict(tenant) -> dict:
        return {
            "id": tenant.id,
            "slug": tenant.slug,
            "name": tenant.name,
            "is_active": tenant.is_active,
            "is_suspended": tenant.is_suspended,
            "suspended_reason": tenant.suspended_reason,
        }
