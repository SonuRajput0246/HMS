"""Platform sign-in, profile and logout.

Mirrors the shape of `auth_service.AuthService` (same `service_response`
returns, same single-live-session rule, same revocation idea) without reusing
its code, because the two authenticate different principals: this one has no
tenant, no menu tree and no role. Sharing the implementation would mean every
line of the tenant path had to learn about a case it does not have.
"""
import uuid
from datetime import datetime, timezone, timedelta

import jwt
from flask import current_app

from src.api.extensions import bcrypt
from src.api.models.super_admin_token_model import SuperAdminToken
from src.api.models.super_admin_user_model import SuperAdminUser
from src.api.middlewares.super_admin_auth import SUPER_ADMIN_MFA_PENDING_SCOPE, SUPER_ADMIN_SCOPE
from src.api.services.audit_service import AuditService
from src.api.utils.mfa import generate_secret, get_uri, verify_otp
from src.api.utils.responses import service_response


class SuperAdminAuthService:
    def __init__(self, db):
        self.db = db
        ## Sign-in, sign-out, password and MFA changes all write here, so the
        ## activity feed covers the security events -- not just the tenant and
        ## operator management ones the other services already recorded.
        self.audit = AuditService(db)

    def login(self, data: dict):
        """Verify credentials and issue a platform token.

        The email lookup is deliberately unfiltered and the failure message
        generic: there is one account class here, so there is nothing to learn
        from "no such account" versus "wrong password".

        Repeated wrong passwords lock the account for a cooling-off window --
        see `_register_failed_attempt`. The lockout is checked *before* the
        password comparison and reports the same event regardless of whether
        the password was right, so a locked account leaks nothing by timing.
        """
        email = data["email"].strip().lower()
        admin = (
            self.db.query(SuperAdminUser)
            .filter(SuperAdminUser.email == email, SuperAdminUser.is_deleted == False)
            .first()
        )

        if admin is not None and self._is_locked(admin):
            self.audit.write(
                admin, "LOGIN_FAILED_SUPER_ADMIN", "super_admin", admin.id,
                {"email": email, "reason": "locked"},
            )
            return service_response(
                False,
                "Too many failed attempts. This account is temporarily locked. "
                "Try again later or ask another administrator to reset it.",
                None,
                429,
            )

        if not admin or not bcrypt.check_password_hash(
            admin.password.encode("utf-8"), data["password"].encode("utf-8")
        ):
            self._register_failed_attempt(admin, email)
            return service_response(False, "Invalid email or password.", None, 401)

        if not admin.is_active:
            ## Credentials were right, so this is not a failed attempt to count.
            self.audit.write(
                admin, "LOGIN_FAILED_SUPER_ADMIN", "super_admin", admin.id,
                {"email": email, "reason": "deactivated"},
            )
            return service_response(
                False, "This account is deactivated. Contact another administrator.", None, 403
            )

        ## A correct password clears the counter, so a few fumbles earlier in
        ## the day do not leave the account one typo away from a lockout.
        self._clear_failed_attempts(admin)

        ## MFA is compulsory for platform administrators, so no account reaches
        ## a session without a second factor. A short-lived pending token stands
        ## in for that session and ties the step that follows to *this* password
        ## attempt; it is also the only path to a session, so a client that
        ## ignores the flag cannot skip the step.
        if admin.mfa_enabled:
            return service_response(
                True,
                "Verification code required.",
                {
                    "mfa_required": True,
                    "mfa_setup_required": False,
                    "temp_token": self._mint_mfa_token(admin),
                },
                200,
            )

        ## Not enrolled yet. Rather than let them in on a password alone, the
        ## sign-in screen is handed a fresh secret to scan and must confirm a
        ## code -- `verify_mfa_login` is what finally flips `mfa_enabled` on and
        ## issues the session.
        secret = generate_secret()
        admin.mfa_secret = secret
        self.db.commit()

        return service_response(
            True,
            "Set up two-factor authentication to continue.",
            {
                "mfa_required": True,
                "mfa_setup_required": True,
                "temp_token": self._mint_mfa_token(admin),
                "qr_uri": get_uri(admin.email, secret),
                "secret": secret,
            },
            200,
        )

    def _issue_session(self, admin: SuperAdminUser):
        """Mint the real platform token, revoke its predecessors, store it.

        Shared by the direct login and the MFA-verified login so the
        single-live-session rule is applied in exactly one place for both.
        """
        access_token = self._mint_token(admin)

        ## Single live session per admin, matching the tenant login. Revoking
        ## the predecessors here is what makes a second sign-in cut the first
        ## off rather than leaving it running alongside.
        self.db.query(SuperAdminToken).filter(
            SuperAdminToken.super_admin_id == admin.id,
            SuperAdminToken.is_revoked == False,
        ).update({"is_revoked": True})

        self.db.add(SuperAdminToken(
            super_admin_id=admin.id,
            access_token=access_token,
            is_revoked=False,
        ))
        self.db.commit()

        self.audit.write(
            admin, "LOGIN_SUPER_ADMIN", "super_admin", admin.id, {"email": admin.email},
        )

        return service_response(
            True,
            "Login successful.",
            {"access_token": access_token, "profile": self.serialize(admin)},
            200,
        )

    ## ------------------------------------------------------ brute-force guard
    @staticmethod
    def _is_locked(admin: SuperAdminUser) -> bool:
        """True while the account's lockout window is still open.

        The column is timezone-aware, but a row read back without an offset is
        treated as UTC rather than compared as if it were local time -- the
        same rule `AuditService` applies to its date filters.
        """
        locked_until = admin.locked_until
        if locked_until is None:
            return False
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        return locked_until > datetime.now(timezone.utc)

    def _register_failed_attempt(self, admin, email: str) -> None:
        """Record a wrong password and lock the account at the ceiling.

        The count is only advanced when the address matched a real account: an
        unknown email has nothing to lock, and persisting a row per bogus
        address would hand an attacker an unbounded write. The attempt is still
        audited either way -- a burst against one address is exactly the signal
        the trail exists to show.
        """
        self.audit.write(
            admin, "LOGIN_FAILED_SUPER_ADMIN", "super_admin",
            admin.id if admin else None,
            {"email": email, "reason": "invalid_credentials"},
            actor_email=email,
        )

        if admin is None:
            return

        admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
        max_attempts = current_app.config.get("SUPER_ADMIN_MAX_LOGIN_ATTEMPTS", 5)
        if admin.failed_login_attempts >= max_attempts:
            lock_minutes = current_app.config.get("SUPER_ADMIN_LOCKOUT_MINUTES", 15)
            admin.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
            ## Reset the counter so the window that follows the lockout starts
            ## clean instead of locking again on the very first wrong password.
            admin.failed_login_attempts = 0
        self.db.commit()

    def _clear_failed_attempts(self, admin: SuperAdminUser) -> None:
        """Forget accumulated failures after a correct password."""
        if admin.failed_login_attempts or admin.locked_until:
            admin.failed_login_attempts = 0
            admin.locked_until = None
            self.db.commit()

    def _mint_mfa_token(self, admin: SuperAdminUser) -> str:
        """A short-lived pending token, valid only to complete MFA. Its scope
        is distinct from the tenant login's `mfa_pending` so the two temporary
        tokens can never be replayed against each other's verify endpoint."""
        return jwt.encode(
            {
                "sub": str(admin.id),
                "scope": SUPER_ADMIN_MFA_PENDING_SCOPE,
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "jti": uuid.uuid4().hex,
            },
            current_app.config["JWT_SECRET_KEY"],
            algorithm=current_app.config["JWT_ALGORITHM"],
        )

    def _mint_token(self, admin: SuperAdminUser) -> str:
        expires_in = current_app.config.get("SUPER_ADMIN_TOKEN_EXPIRES_MIN", 60)
        return jwt.encode(
            {
                ## String subject, per RFC 7519. Parsed back in
                ## middlewares/super_admin_auth.py.
                "sub": str(admin.id),
                "scope": SUPER_ADMIN_SCOPE,
                "email": admin.email,
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_in),
                ## Distinct per issuance, so two sign-ins inside one second
                ## cannot produce byte-identical tokens (see auth_service for
                ## the failure that causes).
                "jti": uuid.uuid4().hex,
            },
            current_app.config["JWT_SECRET_KEY"],
            algorithm=current_app.config["JWT_ALGORITHM"],
        )

    def me(self, admin):
        return service_response(
            True, "Profile fetched successfully.", self.serialize(admin), 200
        )

    def logout(self, admin):
        ## Revokes on the server. Clearing the frontend copy alone would leave
        ## a copied token usable until it expires -- see super_admin_tokens.
        self.db.query(SuperAdminToken).filter(
            SuperAdminToken.super_admin_id == admin.id,
            SuperAdminToken.is_revoked == False,
        ).update({"is_revoked": True})
        self.db.commit()

        self.audit.write(
            admin, "LOGOUT_SUPER_ADMIN", "super_admin", admin.id, {"email": admin.email},
        )
        return service_response(True, "Logged out successfully.", None, 200)

    ## ------------------------------------------------------------------- MFA
    def verify_mfa_login(self, data: dict):
        """Complete an MFA sign-in: prove the pending token, check the code,
        then issue the real session exactly as a direct login would."""
        try:
            payload = jwt.decode(
                data["temp_token"],
                current_app.config["JWT_SECRET_KEY"],
                algorithms=[current_app.config["JWT_ALGORITHM"]],
            )
        except jwt.ExpiredSignatureError:
            return service_response(
                False, "Verification session expired. Please sign in again.", None, 401
            )
        except jwt.InvalidTokenError:
            return service_response(False, "Invalid verification session.", None, 401)

        if payload.get("scope") != SUPER_ADMIN_MFA_PENDING_SCOPE:
            return service_response(False, "Invalid verification session.", None, 401)

        try:
            admin_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            return service_response(False, "Invalid verification session.", None, 401)

        admin = (
            self.db.query(SuperAdminUser)
            .filter(SuperAdminUser.id == admin_id, SuperAdminUser.is_deleted == False)
            .first()
        )
        if not admin:
            return service_response(False, "Administrator not found.", None, 404)
        if not admin.is_active:
            return service_response(
                False, "This account is deactivated. Contact another administrator.", None, 403
            )
        if not admin.mfa_secret:
            return service_response(
                False, "Two-factor authentication is not set up for this account.", None, 400
            )

        if not verify_otp(admin.mfa_secret, data["totp"]):
            self.audit.write(
                admin, "LOGIN_FAILED_SUPER_ADMIN", "super_admin", admin.id,
                {"email": admin.email, "reason": "invalid_mfa_code"},
            )
            return service_response(False, "Invalid verification code.", None, 401)

        ## First sign-in of an account that had not enrolled: the code above is
        ## the proof, so this is where enrolment is committed. Doing it here --
        ## and not when the secret was handed out -- is what stops an abandoned
        ## sign-up from locking the account out with a secret nobody confirmed.
        if not admin.mfa_enabled:
            admin.mfa_enabled = True
            self.db.commit()

        return self._issue_session(admin)

    def setup_mfa(self, admin: SuperAdminUser):
        """Begin (re)enrolling the signed-in admin's authenticator app.

        The new secret replaces the stored one but is left **unenabled** until
        `enable_mfa` confirms a code. Until that code arrives the account reads
        as un-enrolled, so an abandoned reconfigure is not a lockout: the next
        sign-in simply walks through enrolment again (see `login`).
        """
        secret = generate_secret()
        admin.mfa_secret = secret
        admin.mfa_enabled = False
        self.db.commit()

        return service_response(
            True,
            "Scan this in your authenticator app, then confirm the code below.",
            {"qr_uri": get_uri(admin.email, secret), "secret": secret},
            200,
        )

    def enable_mfa(self, admin: SuperAdminUser, data: dict):
        if not admin.mfa_secret:
            return service_response(False, "Start enrolment before confirming a code.", None, 400)
        if not verify_otp(admin.mfa_secret, data["totp"]):
            return service_response(False, "Invalid verification code.", None, 401)

        admin.mfa_enabled = True
        self.db.commit()

        self.audit.write(
            admin, "ENABLE_SUPER_ADMIN_MFA", "super_admin", admin.id, {"email": admin.email},
        )
        return service_response(True, "Two-factor authentication is now on.", None, 200)

    ## -------------------------------------------------------- change password
    def change_password(self, admin: SuperAdminUser, data: dict):
        """Self-service password change. The caller is the admin resolved from
        the token -- no id in the body, so an admin can only change their own.
        The live session is left valid: changing a password is not a reason to
        be signed out of the screen you are standing on."""
        if not bcrypt.check_password_hash(
            admin.password.encode("utf-8"), data["current_password"].encode("utf-8")
        ):
            return service_response(False, "Incorrect current password.", None, 403)

        admin.password = bcrypt.generate_password_hash(data["new_password"], 12).decode("utf-8")
        admin.last_password_update_at = datetime.now(timezone.utc)
        self.db.commit()

        self.audit.write(
            admin, "CHANGE_SUPER_ADMIN_PASSWORD", "super_admin", admin.id,
            {"email": admin.email},
        )
        return service_response(True, "Password updated successfully.", None, 200)

    @staticmethod
    def serialize(admin: SuperAdminUser) -> dict:
        """Wire shape for a platform admin. No password, no MFA secret."""
        return {
            "id": admin.id,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
            "email": admin.email,
            "is_active": admin.is_active,
            "mfa_enabled": admin.mfa_enabled,
            ## While set in the future the account is in a brute-force lockout;
            ## the console reads it to show the operator why a sign-in failed.
            "locked_until": (
                admin.locked_until.isoformat() if admin.locked_until else None
            ),
            "last_password_update_at": (
                admin.last_password_update_at.isoformat()
                if admin.last_password_update_at
                else None
            ),
        }
