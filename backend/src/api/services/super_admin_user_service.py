"""Listing and maintaining the platform's own operators.

A second management surface beside `TenantManagementService`, pointed at
`super_admin_users` instead of `tenants`. Same rules apply: both tables are
global (`BaseModel`), so no tenant is ever resolved and the tenant filter never
touches these queries.

Every action writes an audit row through `AuditService`, so the platform's
activity feed covers the operator lifecycle too -- creating an admin is exactly
the kind of change a trail exists for.

Two self-protection guards are enforced here rather than left to the UI, because
the failure they prevent is locking yourself out of the whole platform:

  * an admin cannot deactivate their own account;
  * an admin cannot reset their own password (that is what the self-service
    change-password is for, and it alone requires the current one).

Password changes and deactivations revoke the target's live tokens, so a reset
or a deactivation takes effect immediately instead of waiting for expiry.
"""
from datetime import datetime, timezone

from sqlalchemy import or_

from src.api.extensions import bcrypt
from src.api.models.super_admin_token_model import SuperAdminToken
from src.api.models.super_admin_user_model import SuperAdminUser
from src.api.services.audit_service import AuditService
from src.api.utils.responses import service_response

ACTIVE = "active"
INACTIVE = "inactive"


class SuperAdminUserService:
    def __init__(self, db):
        self.db = db
        self.audit = AuditService(db)

    ## ----------------------------------------------------------------- read
    def get_admins(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = (data.get("search_value") or "").strip()
        status = data.get("status")

        ## Deactivated accounts stay listed: reactivating one starts by seeing
        ## it. There is no hard delete for an operator.
        query = self.db.query(SuperAdminUser).filter(SuperAdminUser.is_deleted == False)

        if status == ACTIVE:
            query = query.filter(SuperAdminUser.is_active == True)
        elif status == INACTIVE:
            query = query.filter(SuperAdminUser.is_active == False)

        if search_value:
            query = query.filter(
                or_(
                    SuperAdminUser.first_name.like(f"%{search_value}%"),
                    SuperAdminUser.last_name.like(f"%{search_value}%"),
                    SuperAdminUser.email.like(f"%{search_value}%"),
                )
            )

        total_records = query.count()
        admins = (
            query
            .order_by(SuperAdminUser.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        last_page = (total_records + page_size - 1) // page_size if total_records > 0 else 1

        return {
            "status": True,
            "data": [self._serialize(admin) for admin in admins],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size,
            },
        }, 200

    def get_admin_by_id(self, admin_id: int):
        admin = self.db.query(SuperAdminUser).filter(SuperAdminUser.id == admin_id).first()
        if not admin:
            return service_response(False, "Administrator not found.", None, 404)
        return service_response(True, "Administrator fetched successfully.", self._serialize(admin), 200)

    ## ---------------------------------------------------------------- write
    def create_admin(self, data: dict, actor):
        email = data["email"].strip().lower()

        ## Matched WITHOUT `is_deleted`: `ux_super_admin_email` is unique across
        ## the whole column, so even a removed operator's address stays taken.
        ## Checking only live rows would pass validation and then fail the insert.
        if self.db.query(SuperAdminUser).filter(SuperAdminUser.email == email).first() is not None:
            return service_response(False, "An administrator with this email already exists.", None, 409)

        admin = SuperAdminUser(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=email,
            password=bcrypt.generate_password_hash(data["password"], 12).decode("utf-8"),
            is_active=True,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)

        self.audit.write(
            actor, "CREATE_SUPER_ADMIN", "super_admin", admin.id,
            {"email": email, "first_name": admin.first_name, "last_name": admin.last_name},
        )

        return service_response(True, "Administrator created successfully.", self._serialize(admin), 201)

    def update_admin(self, admin_id: int, data: dict, actor):
        admin = self.db.query(SuperAdminUser).filter(SuperAdminUser.id == admin_id).first()
        if not admin:
            return service_response(False, "Administrator not found.", None, 404)
        if admin.is_deleted:
            return service_response(False, "This administrator has been removed.", None, 400)
        if not data:
            return service_response(False, "No changes supplied.", None, 400)

        changed = {}

        if "first_name" in data and data["first_name"] != admin.first_name:
            changed["first_name"] = {"from": admin.first_name, "to": data["first_name"]}
            admin.first_name = data["first_name"]

        if "last_name" in data and data["last_name"] != admin.last_name:
            changed["last_name"] = {"from": admin.last_name, "to": data["last_name"]}
            admin.last_name = data["last_name"]

        if "email" in data:
            email = data["email"].strip().lower()
            if email != admin.email:
                ## The unique index covers the whole column, so an address held
                ## by a removed account still clashes -- same rule as create.
                clash = (
                    self.db.query(SuperAdminUser)
                    .filter(SuperAdminUser.email == email, SuperAdminUser.id != admin.id)
                    .first()
                )
                if clash is not None:
                    return service_response(False, "An administrator with this email already exists.", None, 409)
                changed["email"] = {"from": admin.email, "to": email}
                admin.email = email

        if not changed:
            return service_response(True, "Nothing changed.", self._serialize(admin), 200)

        self.db.commit()
        self.db.refresh(admin)

        self.audit.write(actor, "UPDATE_SUPER_ADMIN", "super_admin", admin.id, {"changed": changed})

        return service_response(True, "Administrator updated successfully.", self._serialize(admin), 200)

    def set_admin_status(self, admin_id: int, is_active: bool, actor):
        admin = (
            self.db.query(SuperAdminUser)
            .filter(SuperAdminUser.id == admin_id, SuperAdminUser.is_deleted == False)
            .first()
        )
        if not admin:
            return service_response(False, "Administrator not found.", None, 404)

        if getattr(actor, "id", None) == admin.id:
            return service_response(
                False, "You cannot deactivate your own account.", None, 400
            )

        if admin.is_active == is_active:
            return service_response(True, "Nothing changed.", self._serialize(admin), 200)

        admin.is_active = is_active
        if not is_active:
            ## A deactivated operator's token must stop working now, not at
            ## expiry. The guard re-checks is_active, but revoking here closes
            ## the window for a copied token too.
            self._revoke_tokens(admin.id)
        self.db.commit()
        self.db.refresh(admin)

        self.audit.write(
            actor,
            "ACTIVATE_SUPER_ADMIN" if is_active else "DEACTIVATE_SUPER_ADMIN",
            "super_admin",
            admin.id,
            {"email": admin.email, "is_active": is_active},
        )

        message = "Administrator activated successfully." if is_active else "Administrator deactivated successfully."
        return service_response(True, message, self._serialize(admin), 200)

    def reset_admin_password(self, admin_id: int, data: dict, actor):
        """Set a new password on an operator's behalf (recovery by another
        admin). Self-service change, which needs the current password, is the
        only path an admin has to their own."""
        admin = (
            self.db.query(SuperAdminUser)
            .filter(SuperAdminUser.id == admin_id, SuperAdminUser.is_deleted == False)
            .first()
        )
        if not admin:
            return service_response(False, "Administrator not found.", None, 404)

        if getattr(actor, "id", None) == admin.id:
            return service_response(
                False,
                "Use Change password to set your own password; a reset needs your current one.",
                None,
                400,
            )

        admin.password = bcrypt.generate_password_hash(data["new_password"], 12).decode("utf-8")
        admin.last_password_update_at = datetime.now(timezone.utc)
        ## Resetting a password signs the operator out anywhere they are signed
        ## in, so a recovery cannot leave an old session running.
        self._revoke_tokens(admin.id)
        self.db.commit()

        self.audit.write(
            actor, "RESET_SUPER_ADMIN_PASSWORD", "super_admin", admin.id,
            {"email": admin.email},
        )

        return service_response(True, "Password reset successfully.", None, 200)

    def reset_admin_mfa(self, admin_id: int, actor):
        """Clear another operator's authenticator (recovery by another admin).

        MFA is compulsory, so an administrator who loses their device cannot
        sign in at all -- and `reset_admin_password` alone does not help,
        because the account still demands a code from the lost app. This is the
        other half of recovery: it drops the secret and the enrolled flag, so
        the next sign-in walks through compulsory enrolment again (see
        `SuperAdminAuthService.login`). The target's live sessions are revoked,
        so a recovery cannot leave a session running on the strength of the
        factor that was just removed.
        """
        admin = (
            self.db.query(SuperAdminUser)
            .filter(SuperAdminUser.id == admin_id, SuperAdminUser.is_deleted == False)
            .first()
        )
        if not admin:
            return service_response(False, "Administrator not found.", None, 404)

        if getattr(actor, "id", None) == admin.id:
            return service_response(
                False,
                "Use the Security page to reconfigure your own two-factor authentication.",
                None,
                400,
            )

        if not admin.mfa_enabled and not admin.mfa_secret:
            return service_response(
                True, "Two-factor authentication was not set up.", self._serialize(admin), 200
            )

        admin.mfa_secret = None
        admin.mfa_enabled = False
        self._revoke_tokens(admin.id)
        self.db.commit()
        self.db.refresh(admin)

        self.audit.write(
            actor, "RESET_SUPER_ADMIN_MFA", "super_admin", admin.id,
            {"email": admin.email},
        )

        return service_response(
            True,
            "Two-factor authentication reset. The administrator must enrol again at next sign-in.",
            self._serialize(admin),
            200,
        )

    ## -------------------------------------------------------------- helpers
    def _revoke_tokens(self, admin_id: int) -> None:
        self.db.query(SuperAdminToken).filter(
            SuperAdminToken.super_admin_id == admin_id,
            SuperAdminToken.is_revoked == False,
        ).update({"is_revoked": True})

    @staticmethod
    def _serialize(admin: SuperAdminUser) -> dict:
        def _iso(value):
            return value.isoformat() if value else None

        return {
            "id": admin.id,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
            "email": admin.email,
            "is_active": admin.is_active,
            "is_deleted": admin.is_deleted,
            "mfa_enabled": admin.mfa_enabled,
            "locked_until": _iso(admin.locked_until),
            "last_password_update_at": _iso(admin.last_password_update_at),
            "created_at": _iso(admin.created_at),
            "updated_at": _iso(admin.updated_at),
        }
