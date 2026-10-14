import logging
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from flask import current_app, request
from sqlalchemy import select
from src.api.extensions import bcrypt
from src.api.models import EmailOTP, Token, Module, RoleModuleAccess, Role
from src.api.models.user_model import User
from src.api.schemas.auth_schema import LoginResponseSchema
from src.api.utils.mfa import generate_secret, get_uri, verify_otp
from src.api.utils.security import hash_value
from src.api.utils.responses import service_response
from src.api.utils.errors import ResourceConflictError, APIError
from src.api.services.email_service import EmailService
from src.database.tenant_context import current_tenant_id

class AuthService:

    def __init__(self, db):
        self.db = db


    def register_user(self, data: dict):
        try:
            ## 1. Check for existing user
            stmt = select(User).filter_by(is_deleted=False, email=data['email'])
            existing_user = self.db.execute(stmt).scalar_one_or_none()
            if existing_user:
                raise ResourceConflictError("Your account already exists with this email.")

            ## 2. Resolve the role public registration grants.
            ##
            ## This was `role_id=1`, which in a freshly provisioned hotel is the
            ## first-seeded role -- SUPER_ADMIN. So anyone who could reach
            ## /register could sign themselves up as the hotel's top
            ## administrator. The Role read is tenant-scoped by the Phase 3
            ## filter, so this resolves the *current hotel's* GUEST role; a
            ## self-registered account therefore has no staff access anywhere.
            guest_role = (
                self.db.query(Role)
                .filter(Role.role_code == "GUEST", Role.is_deleted == False)
                .first()
            )
            if guest_role is None:
                ## A provisioning fault, not a user error: every hotel is seeded
                ## with GUEST before it is reachable. Refusing is the safe
                ## failure -- granting some other role would be the bug we are
                ## fixing.
                raise RuntimeError(
                    "This hotel has no GUEST role, so self-registration is "
                    "closed. Ask an administrator to create your account."
                )

            ## 3. Hash Password
            hashed_password = bcrypt.generate_password_hash(data['password'], 12).decode("utf-8")

            ## 4. Create User instance
            new_user = User(
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                password=hashed_password,
                role_id=guest_role.id,
                is_email_verified=False,
                is_active=True
            )

            self.db.add(new_user)
            self.db.flush()

            ## 5. Handle OTP Sending via EmailService
            email_service = EmailService(self.db)
            email_sent = email_service.send_email_verification_otp(new_user)

            if not email_sent:
                raise RuntimeError("Failed to send verification email")

            ## 6. Commit only if everything succeeded
            self.db.commit()

            return service_response(
                True,
                "Registration successful. Please check your email for the OTP.",
                None,
                201
            )

        except ResourceConflictError:
            self.db.rollback()
            raise

        except Exception as e:
            self.db.rollback()
            logging.exception(f"Registration Error: {str(e)}")
            raise APIError("An internal error occurred during registration.")


    def verify_email(self, data: dict):
        user = self.db.query(User).filter_by(is_deleted=False, email=data['email']).first()
        if not user:
            return {"status": False, "message": "User not found.", "code": 404}

        otp_record = self.db.query(EmailOTP).filter_by(
                user_id=user.id, is_used=False, otp_purpose='EMAIL_VERIFICATION'
            ).order_by(EmailOTP.created_at.desc()).first()

        if not otp_record:
            return {"status": False, "message": "No active OTP found. Please request a new one.", "code": 404}

        if datetime.now(timezone.utc) > otp_record.expires_at.replace(tzinfo=timezone.utc):
            return {"status": False, "message": "OTP expired. Please request a new one.", "code": 409}

        if otp_record.attempts >= current_app.config["OTP_ATTEMPTS"]:
            return {"status": False, "message": "Too many failed attempts. Request a new OTP.", "code": 429}

        provided_otp_hash = hash_value(str(data['otp']))
        if provided_otp_hash != otp_record.otp_hash:
            otp_record.attempts += 1
            self.db.commit()
            return {"status": False, "message": "Invalid OTP.", "code": 401}

        otp_record.is_used = True
        user.is_email_verified = True
        self.db.commit()
        return {"status": True, "message": "Email verified. Login successful.", "data": user, "code": 200}



    def generate_user_session(self, user):
        """Helper to generate tokens and format the login response."""
        access_exp = datetime.now(timezone.utc) + timedelta(minutes=current_app.config["JWT_ACCESS_TOKEN_EXPIRES_MIN"])
        access_token = jwt.encode(
            {
                "user_id": user.id,
                ## The hotel this token is good for. authenticate() refuses a
                ## token whose claim does not match the tenant the request
                ## resolved to, so a token minted at acme is structurally
                ## useless at globex even if its bearer presents it there.
                "tenant_id": user.tenant_id,
                "iat": datetime.now(timezone.utc),
                "exp": access_exp,
                # jti makes each issuance distinct.
                #
                # Without it the payload is only {user_id, iat, exp}, and iat
                # has one-second granularity, so two logins inside the same
                # second signed byte-identical tokens. That broke the single
                # live-token rule below in a way revocation cannot see: the
                # second login revoked the first token row and then inserted a
                # new row carrying the same access_token string, so the old
                # token was live again immediately. Two sessions survived a
                # re-login whenever both logins fell within one second.
                "jti": uuid.uuid4().hex,
            },
            current_app.config["JWT_SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"]
        )

        refresh_exp = datetime.now(timezone.utc) + timedelta(days=current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"])
        refresh_token = jwt.encode(
            {"user_id": user.id, "tenant_id": user.tenant_id,
             "iat": datetime.now(timezone.utc),
             "exp": refresh_exp, "jti": uuid.uuid4().hex},
            current_app.config["JWT_SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"]
        )

        ## Revoke old tokens & store new one
        ##
        ## The filter has to match the LIVE tokens. A bare `Token.is_revoked`
        ## renders as `is_revoked = 1`, which selects the already-revoked rows
        ## and re-revokes them -- a no-op that reads as though it worked. Every
        ## login therefore left its predecessor's token live, so a signed-in
        ## session survived indefinitely and signing in again did not sign the
        ## earlier session out. Written as `== False` to match logout, the
        ## refresh path and user_account_service, which all compare explicitly.
        self.db.query(Token).filter(
            Token.user_id == user.id,
            Token.is_revoked == False,
        ).update({"is_revoked": True})
        new_token = Token(
            user_id=user.id,
            access_token=access_token,
            refresh_token_hash=hash_value(refresh_token),
            is_revoked=False,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(new_token)
        self.db.commit()

        ## Serialize user data
        user_schema = LoginResponseSchema()
        user_data = user_schema.dump(user)

        ## Build menu_access from role_module_access (one row per
        ## role + module + operation_key), joined to modules for menu details.
        menu_access = self._build_menu_access(user.role_id)

        return {
            "user_data": {**user_data, "access_token": access_token, "menu_access": menu_access},
            "refresh_token": refresh_token
        }

    def _build_menu_access(self, role_id):
        """
        Builds the menu_access list for a role.

        Access rows live in role_module_access, one per operation_key. The
        operation's display name comes from the module's access_json, which
        holds the per-module wording (e.g. operation_key 'Create' displays as
        'Add User'), so the response keeps both names it always returned:
        operation_name (the generic key) and operation_display_name (the
        module-specific label).
        """
        accesses = (
            self.db.query(RoleModuleAccess)
            .filter(
                RoleModuleAccess.role_id == role_id,
                RoleModuleAccess.is_active == True,
                RoleModuleAccess.is_deleted == False,
            )
            .all()
        )

        if not accesses:
            return []

        ## One query for every module involved, instead of one per module
        module_ids = {access.module_id for access in accesses}
        modules = (
            self.db.query(Module)
            .filter(
                Module.id.in_(module_ids),
                Module.is_active == True,
                Module.is_deleted == False,
            )
            .order_by(Module.display_order_no.asc())
            .all()
        )

        ## module_id -> operation_key -> row, so building each access_list is
        ## a dict lookup rather than a scan over all rows
        accesses_by_module = {}
        for access in accesses:
            accesses_by_module.setdefault(access.module_id, {})[access.operation_key] = access

        menu_access = []

        for module in modules:
            module_ops = accesses_by_module.get(module.id, {})
            if not module_ops:
                continue

            ## access_json defines the display wording and the intended order
            ## for this module's operations. Iterating it keeps the frontend
            ## list stable (View first, then Create, Edit, Delete).
            display_names = {}
            order_index = {}
            for position, entry in enumerate(module.access_json or []):
                operation_key = entry.get("operation_key")
                if operation_key is None:
                    continue
                display_names[operation_key] = entry.get("key") or operation_key
                order_index.setdefault(operation_key, position)

            access_list = []
            for operation_key, access in module_ops.items():
                access_list.append({
                    "sort": order_index.get(operation_key, len(order_index)),
                    "entry": {
                        "id": access.id,
                        "is_active": True,
                        "operation_name": operation_key,
                        "operation_display_name": display_names.get(operation_key, operation_key),
                    },
                })

            access_list.sort(key=lambda item: item["sort"])
            access_list = [item["entry"] for item in access_list]

            menu_access.append({
                "route_path": module.route_path,
                "icon": module.icon,
                "module_id": module.id,
                "access_list": access_list,
                "module_name": module.module_name,
                "has_child_menu": module.has_child_menu,
                "display_order_no": module.display_order_no,
                "menu_parent_code": module.menu_parent_code,
                "module_display_name": module.module_display_name
            })

        return menu_access


    def initiate_setup_mfa(self, user_id):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return service_response(False, "User not found.", None, 404)

        ## Generate secret
        secret = generate_secret()

        ## Save TEMP (important: not enabled yet)
        user.mfa_secret = secret
        self.db.commit()

        ## Generate URI
        uri = get_uri(user.email, secret)

        data = {"qr_uri": uri, "secret": secret}
        return service_response(True, "MFA initiated successfully.", data, 200)


    def verify_and_enable_mfa(self, payload):
        user_id = payload.get("userId")
        otp = payload.get("totp")

        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return service_response(False, "User not found", None, 404)

        if not user.mfa_secret:
            return service_response(False, "MFA not enabled", None, 404)

        if verify_otp(user.mfa_secret, otp):
            user.mfa_enabled = True
            self.db.commit()
            return service_response(True, "MFA enabled successfully", None, 200)
        return service_response(False, "Invalid OTP", None, 401)


    def disable_mfa(self, user_id):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return service_response(False, "User not found", None, 404)

        user.mfa_secret = None
        user.mfa_enabled = False
        self.db.commit()
        return service_response(True, "MFA disabled successfully.", None, 200)


    def user_login(self, data):
        user = self.db.query(User).filter_by(is_deleted=False, email=data['email']).first()
        if not user or not bcrypt.check_password_hash(user.password.encode('utf-8'), data['password'].encode('utf-8')):
            return {"status": False, "message": "Invalid email or password.", "code": 401}

        if not user.is_active:
            is_user_deactivated = (user.deactivated_by == 'user')
            msg = "Account inactive." if is_user_deactivated else "Account deactivated. Contact admin."
            return {"status": False, "message": msg, "ask_account_activation": is_user_deactivated, "code": 403}

        if not user.is_email_verified:
            email_service = EmailService(self.db)
            email_sent = email_service.send_email_verification_otp(user)
            msg = "Please check your email for the OTP." if email_sent else "Failed to sent verification email. Request a new OTP."
            return {"status": False, "message": msg, "start_email_verification": True, "code": 403}

        if user.mfa_enabled:
            temp_token_payload = {
                "user_id": user.id,
                "tenant_id": user.tenant_id,
                "scope": "mfa_pending",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5)  # Short expiry
            }

            temp_token = jwt.encode(temp_token_payload, current_app.config["JWT_SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])

            user_data = {
                "mfa_enabled": True,
                "temp_token": temp_token
            }
            return {"status": True, "is_session_req": False, "message": "Login successful. Initiate MFA.", "data": user_data, "code": 200}
        return {"status": True, "is_session_req": True, "message": "Login successful.", "data": user}


    def verify_mfa_login(self, payload):
        otp = payload.get("totp")
        temp_token = payload.get("temp_token")

        try:
            decoded_payload = jwt.decode(
                temp_token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=[current_app.config.get("JWT_ALGORITHM", "HS256")]
            )

            if decoded_payload.get("scope") != "mfa_pending":
                return {"status": False, "message": "Invalid token scope.", "code": 401}

            ## Same binding as the access and refresh tokens. The temp token is
            ## short-lived but it is still a bearer credential, so it is refused
            ## on a host it was not minted for.
            tenant_id = current_tenant_id()
            if tenant_id is None or decoded_payload.get("tenant_id") != tenant_id:
                return {"status": False, "message": "This MFA session belongs to another hotel.", "code": 401}

            user_id = decoded_payload.get("user_id")
            user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()

            if not user:
                return {"status": False, "message": "User not found", "code": 404}

            if not user.mfa_secret:
                return {"status": False, "message": "MFA not initiated", "code": 400}

            if verify_otp(user.mfa_secret, otp):
                return {"status": True, "message": "TOTP verified successfully", "data": user}
            return {"status": False, "message": "Invalid OTP", "code": 401}
        except jwt.ExpiredSignatureError:
            return {"status": False, "message": "MFA session expired. Please login again.", "code": 401}
        except jwt.InvalidTokenError:
            return {"status": False, "message": "Invalid or corrupted MFA token.", "code": 401}


    def send_otp_on_email(self, data):
        user = self.db.query(User).filter_by(email=data['email'], is_deleted=False).first()
        if not user:
            return {"status": False, "message": "User not found"}, 404

        email_service = EmailService(self.db)
        if data['otp_type'] == 'account_activation':
            activation_email_sent = email_service.send_account_activation_otp(user)
            msg = "OTP sent. Please check your email." if activation_email_sent else "Failed to send account activation email. Please request a new OTP."
        elif data['otp_type'] == 'reset_password':
            reset_password_email_sent = email_service.send_password_reset_otp(user)
            msg = "OTP sent. Please check your email." if reset_password_email_sent else "Failed to send OTP on email. Please request a new OTP."
        else:
            verification_email_sent = email_service.send_email_verification_otp(user)
            msg = "OTP sent. Please check your email." if verification_email_sent else "Failed to send verification email. Please request a new OTP."
        return service_response(True, msg, None, 200)


    def activate_account(self, data):
        user = self.db.query(User).filter_by(is_deleted=False, email=data['email']).first()
        if not user:
            return {"error": "User not found.", "code": 404}

        otp_record = self.db.query(EmailOTP).filter_by(
                user_id=user.id, is_used=False, otp_purpose="ACCOUNT_ACTIVATION"
            ).order_by(EmailOTP.created_at.desc()).first()

        if not otp_record:
            return {"error": "No active OTP found. Please request a new one.", "code": 404}

        if datetime.now(timezone.utc) > otp_record.expires_at.replace(tzinfo=timezone.utc):
            return {"error": "OTP expired. Please request a new one.", "code": 409}

        if otp_record.attempts >= current_app.config["OTP_ATTEMPTS"]:
            return {"error": "Too many failed attempts. Request a new OTP.", "code": 429}

        provided_otp_hash = hash_value(str(data['otp']))
        if provided_otp_hash != otp_record.otp_hash:
            otp_record.attempts += 1
            self.db.commit()
            return {"error": "Invalid OTP.", "code": 401}

        otp_record.is_used = True
        user.is_email_verified = True
        if user.deactivated_by == 'user':
            user.is_active = True
        self.db.commit()
        return {"user": user}



    def get_fresh_tokens(self):
        ## Read refresh token from HttpOnly cookie
        refresh_token = request.cookies.get("hms_refreshToken")
        if not refresh_token:
            return {"error": "No refresh token found.", "code": 400}

        ## Decode refresh token (expiry checked here)
        payload = jwt.decode(refresh_token, current_app.config["JWT_SECRET_KEY"], algorithms=current_app.config["JWT_ALGORITHM"])

        user_id = payload.get("user_id")
        if not user_id:
            return {"error": "Invalid refresh token.", "code": 401}

        ## The refresh cookie rides on whatever host the browser is talking to.
        ## In development two hotels share localhost, so the same cookie is sent
        ## for both; the claim is what stops acme's cookie from refreshing a
        ## session at globex. Checked before the user is loaded.
        tenant_id = current_tenant_id()
        if tenant_id is None or payload.get("tenant_id") != tenant_id:
            return {"error": "Refresh token is not valid for this hotel.", "code": 401}

        ## Validate user.
        ## NOTE: deliberately no `is_active` filter, so a token issued before a
        ## user was deactivated still redeems. If that is not intended, add
        ## `is_active=True` back.
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return {"error": "User not found.", "code": 404}

        ## Validate refresh token from DB (Hashed)
        db_token = self.db.query(Token).filter_by(
            user_id=user.id,
            refresh_token_hash=hash_value(refresh_token),
            is_revoked=False
        ).first()
        if not db_token:
            return {"error": "Refresh token revoked or invalid.", "code": 401}

        return {"user": user}


    def reset_user_password(self, data):
        user = self.db.query(User).filter_by(is_deleted=False, email=data['email']).first()
        if not user:
            return service_response(False, "User not found", None, 404)

        otp_record = self.db.query(EmailOTP).filter_by(
                user_id=user.id, is_used=False, otp_purpose='RESET_PASSWORD'
            ).order_by(EmailOTP.created_at.desc()).first()

        if not otp_record:
            return service_response(False, "No active OTP found. Please request a new one.", None, 404)

        if datetime.now(timezone.utc) > otp_record.expires_at.replace(tzinfo=timezone.utc):
            return service_response(False, "OTP expired. Please request a new one.", None, 409)

        if otp_record.attempts >= current_app.config["OTP_ATTEMPTS"]:
            return service_response(False, "Too many failed attempts. Request a new OTP.", None, 429)

        provided_otp_hash = hash_value(str(data['otp']))
        if provided_otp_hash != otp_record.otp_hash:
            otp_record.attempts += 1
            self.db.commit()
            return service_response(False, "Invalid OTP.", None, 401)

        otp_record.is_used = True
        hashed_password = bcrypt.generate_password_hash(data['password'], 12).decode("utf-8")
        user.password = hashed_password
        user.last_password_update_at = datetime.now(timezone.utc)
        self.db.commit()
        return service_response(True, "Password updated successfully.", None, 200)


    def logout_user(self, user_id):
        stmt = select(User).filter_by(is_deleted=False, id=user_id)
        user = self.db.execute(stmt).scalar_one_or_none()
        if not user:
            return {"error": "User not found.", "code": 404}
        self.db.query(Token).filter(
            Token.user_id == user_id,
            Token.is_revoked == False
        ).update({"is_revoked": True})
        self.db.commit()
        return {"is_success": True}