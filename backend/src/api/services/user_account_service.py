from datetime import datetime, timezone
from src.api.extensions import bcrypt
from src.api.models import AccountDeletions, Token
from src.api.models.user_model import User
from src.api.services.enum_service import EnumService
from src.api.utils.common_helper import normalize_text
from src.api.utils.responses import service_response


class UserAccountService:
    def __init__(self, db):
        self.db = db
        self.enum_service = EnumService(db)


    def update_user_profile(self, user_id: int, data: dict):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return service_response(False, "User not found", None, 404)
        user.first_name = data.get("first_name")
        user.last_name = data.get("last_name")
        self.db.commit()
        return service_response(True, "Your profile updated successfully", None, 200)


    def update_user_password(self, user_id, data):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return service_response(False, "User not found", None, 404)

        ## Verify current password
        if not bcrypt.check_password_hash(
            user.password.encode("utf-8"),
            data["current_password"].encode("utf-8")
        ):
            return service_response(False, "Incorrect current password", None, 403)

        ## Hash new password
        hashed_password = bcrypt.generate_password_hash(
            data["new_password"], 12
        ).decode("utf-8")
        user.password = hashed_password
        user.last_password_update_at = datetime.now(timezone.utc)
        self.db.commit()
        return service_response(True, "Password updated successfully", None, 200)


    def deactivate_user(self, user_id: int, data: dict):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return {"error": "User not found.", "code": 404}

        ## Validated against enum_options, so a new option is a seeder change
        ## only. Self-deactivation is always "user".
        error = self.enum_service.validate("account_deactivated_by", "user")
        if error:
            return service_response(False, error, None, 500)

        user.is_active = False
        user.deactivated_by = "user"
        user.deactivation_reason = normalize_text(
            data.get("deactivation_reason"),
            "Deactivated by user"
        )
        self.db.query(Token).filter(
            Token.user_id == user_id,
            Token.is_revoked == False
        ).update({"is_revoked": True})
        self.db.commit()
        return {"is_success": True}


    def delete_my_account(self, user_id: int, data: dict):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return {"error": "User not found.", "code": 404}

        if not bcrypt.check_password_hash(user.password.encode('utf-8'), data['password'].encode('utf-8')):
            return {"error": "Provided password is incorrect", "code": 403}

        ## Check for any active reservation and user role
        ## If not any active reservations user role is "guest" (match role id)
        isActiveReservationAvailable = False
        ### Add this check in deactivate use also

        ## Validate the enum-backed columns before writing. Keys must match
        ## enum_options.option_key exactly (lowercase), which the previous
        ## "APPROVED"/"USER" values did not - they were rejected by the
        ## CheckConstraint at INSERT time.
        errors = self.enum_service.validate_model(
            "account_deletions",
            {
                "account_deletion_status": "approved",
                "account_deleted_by": "user",
            },
        )
        if errors:
            return service_response(
                False, next(iter(errors.values())), None, 400
            )

        if not isActiveReservationAvailable and user.role_id == 1:
            deletion_request = AccountDeletions(
                user_id=user_id,
                reason=data.get("deletion_reason"),
                requested_at=datetime.now(timezone.utc),
                account_deletion_status="approved",
                account_deleted_by="user",
                account_deleted_at=datetime.now(timezone.utc)
            )
            self.db.add(deletion_request)
            user.is_active = False
            user.is_deleted = True
            user.deleted_at = datetime.now(timezone.utc)

            self.db.query(Token).filter(
                Token.user_id == user_id,
                Token.is_revoked == False
            ).update({"is_revoked": True})
            self.db.commit()
            return {"revoke_session": True}
        else:
            deletion_request = AccountDeletions(
                user_id=user_id,
                reason=data.get("deletion_reason"),
                requested_at=datetime.now(timezone.utc),
                account_deletion_status="pending",
                account_deleted_by=None,
            )
            self.db.add(deletion_request)
            self.db.commit()
            return {"revoke_session": False}

