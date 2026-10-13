import logging
import random
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import update

from src.api.models.email_otp_model import EmailOTP
from src.api.services.template_resolver import TemplateResolver
from src.api.utils.email_helper import send_email
from src.api.utils.security import hash_value
from src.api.utils.template_codes import TemplateCode, TemplateVariable


logger = logging.getLogger(__name__)


class EmailService:
    """Issues OTPs and delivers them through the DB-driven template store.

    The public method signatures and return contract are UNCHANGED from the
    previous implementation, so `auth_service.py` needs no edits:

        send_email_verification_otp(user) -> bool
        send_account_activation_otp(user) -> bool
        send_password_reset_otp(user)     -> bool

    What changed is the subject and body, which now come from the
    `message_templates` table instead of `templates/emails/*.html` and
    hardcoded string literals.

    FAILURE POLICY
    --------------
    The return value reflects whether SMTP actually accepted the message, not
    whether the stored template was used. If a template row is missing,
    inactive, or unrenderable, the resolver substitutes safe fallback copy,
    logs an ERROR, and the mail still goes out.

    The alternative -- returning False on fallback -- was rejected because
    `auth_service` treats False as fatal: it raises RuntimeError on
    registration and tells the user the mail failed. A typo in a template
    would then block password resets outright, which is a worse outcome than
    sending a correct-if-plain email. The loud log plus the resolver's
    `is_fallback` flag is the signal to act on.
    """

    def __init__(self, db):
        self.db = db
        self.resolver = TemplateResolver(db)


    def generate_otp(self):
        return str(random.randint(100000, 999999))


    # ---------------------------------------------------------------
    # PUBLIC API (unchanged signatures)
    # ---------------------------------------------------------------

    def send_email_verification_otp(self, user):
        """Generate, persist, and email an EMAIL_VERIFICATION OTP."""
        otp_expiry_minutes = current_app.config["OTP_EXPIRY_MINUTES"]

        ## 1. Invalidate any previously issued, still-unused OTP
        self._invalidate_open_otps(user.id, "EMAIL_VERIFICATION")

        ## 2. Generate and store the new OTP
        otp = self.generate_otp()
        self._store_otp(user.id, otp, "EMAIL_VERIFICATION", otp_expiry_minutes)

        ## 3. Resolve the template and send
        return self._dispatch(
            code=TemplateCode.EMAIL_VERIFICATION_OTP,
            user=user,
            otp=otp,
            otp_expiry_minutes=otp_expiry_minutes,
        )

    def send_account_activation_otp(self, user):
        """Generate, persist, and email an ACCOUNT_ACTIVATION OTP."""
        otp_expiry_minutes = current_app.config["OTP_EXPIRY_MINUTES"]

        self._invalidate_open_otps(user.id, "ACCOUNT_ACTIVATION")

        otp = self.generate_otp()
        self._store_otp(user.id, otp, "ACCOUNT_ACTIVATION", otp_expiry_minutes)

        return self._dispatch(
            code=TemplateCode.ACCOUNT_ACTIVATION_OTP,
            user=user,
            otp=otp,
            otp_expiry_minutes=otp_expiry_minutes,
        )

    def send_password_reset_otp(self, user):
        """Generate, persist, and email a RESET_PASSWORD OTP."""
        otp_expiry_minutes = current_app.config["OTP_EXPIRY_MINUTES"]

        self._invalidate_open_otps(user.id, "RESET_PASSWORD")

        otp = self.generate_otp()
        self._store_otp(user.id, otp, "RESET_PASSWORD", otp_expiry_minutes)

        return self._dispatch(
            code=TemplateCode.PASSWORD_RESET_OTP,
            user=user,
            otp=otp,
            otp_expiry_minutes=otp_expiry_minutes,
        )


    # ---------------------------------------------------------------
    # OTP PERSISTENCE
    # ---------------------------------------------------------------

    def _invalidate_open_otps(self, user_id, otp_purpose):
        """Mark this user's previously issued, unused OTPs as consumed."""
        stmt = (
            update(EmailOTP)
            .where(
                EmailOTP.user_id == user_id,
                EmailOTP.is_used == False,
                EmailOTP.otp_purpose == otp_purpose,
            )
            .values(is_used=True)
        )
        self.db.execute(stmt)

    def _store_otp(self, user_id, otp, otp_purpose, otp_expiry_minutes):
        """Persist a hashed OTP.

        `expires_at` MUST be set here: the column is NOT NULL with no database
        default, and `auth_service.verify_email` compares against it. The
        previous implementation omitted it, so every OTP insert failed with
        IntegrityError (1048) and no OTP could ever be issued.
        """
        now = datetime.now(timezone.utc)

        otp_record = EmailOTP(
            user_id=user_id,
            otp_hash=hash_value(otp),
            otp_purpose=otp_purpose,
            expires_at=now + timedelta(minutes=otp_expiry_minutes),
            attempts=0,
            is_used=False,
            created_at=now,
            updated_at=now,
        )
        self.db.add(otp_record)
        self.db.commit()

        return otp_record


    # ---------------------------------------------------------------
    # DELIVERY
    # ---------------------------------------------------------------

    def _build_context(self, user, otp, otp_expiry_minutes) -> dict:
        """Values made available to `{{ variable }}` tokens.

        Keys are TemplateVariable values so the seeder, the CRUD validator,
        and this call site cannot drift apart. `company_name` is included as a
        context-only convenience for admins writing new templates; it is not
        part of OTP_VARIABLES.
        """
        return {
            TemplateVariable.USER_NAME.value: f"{user.first_name} {user.last_name}",
            TemplateVariable.OTP.value: otp,
            TemplateVariable.EXPIRY_MINUTES.value: otp_expiry_minutes,
            "company_name": current_app.config.get("COMPANY_NAME", "HMS"),
        }

    def _dispatch(self, code, user, otp, otp_expiry_minutes) -> bool:
        """Resolve the email template for `code` and send it.

        Returns True only if SMTP accepted the message. A template fallback
        still counts as a successful send -- see the class docstring.
        """
        context = self._build_context(user, otp, otp_expiry_minutes)

        try:
            rendered = self.resolver.render_email(code, context)
        except Exception:
            ## render_email is already fail-safe, so reaching here means a bug
            ## in the resolver itself. Swallow it rather than failing the auth
            ## request, but make it very visible.
            logger.exception(
                "EmailService: template resolution raised unexpectedly for %s",
                getattr(code, "value", code),
            )
            return False

        if rendered.get("is_fallback"):
            logger.error(
                "EmailService: sending %s to %s using FALLBACK copy "
                "(template_id=%s). Check the message_templates row for code '%s' "
                "and channel 'email'.",
                getattr(code, "value", code), user.email,
                rendered.get("template_id"), getattr(code, "value", code),
            )
        elif rendered.get("missing_variables"):
            logger.warning(
                "EmailService: %s rendered with %d unfilled variable(s): %s",
                getattr(code, "value", code),
                len(rendered["missing_variables"]),
                ", ".join(rendered["missing_variables"]),
            )

        subject = rendered.get("subject") or "HMS Notification"
        html_body = rendered.get("html_body")

        if not html_body:
            logger.error(
                "EmailService: refusing to send an empty body for %s",
                getattr(code, "value", code),
            )
            return False

        return send_email(user.email, subject, html_body)