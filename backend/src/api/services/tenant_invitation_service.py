"""The invitation lifecycle: issue -> email -> accept, for a tenant's admin.

This is step 3-6 of tenant onboarding, kept in one module because the three
stages share a secret (the raw token) and a rule (single-use):

  issue   -- `create_invitation` mints a `secrets.token_urlsafe` token,
             stores only its SHA-256, and soft-deletes any earlier live
             invitation for the tenant, so at most one link is outstanding;
  email   -- `send_invitation` renders TENANT_ADMIN_INVITATION from the
             tenant's own template row and posts the link to the invited
             address;
  accept  -- `accept` re-hashes the presented token, verifies it against the
             row, then creates the tenant-scoped user AND stamps
             `accepted_at` in ONE transaction -- the account and its claim
             on the invitation commit together or not at all.

WHY THE USER DOES NOT EXIST UNTIL ACCEPTANCE
--------------------------------------------
On the invitation path (the default) nobody has a password to store at issue
time, and a pre-created, not-yet-claimed account would sit in the tenant's
user list with a placeholder credential nobody should ever be able to sign
in with. So the row in `users` is born here, at acceptance,
`is_email_verified=True` -- the click through an emailed link IS the
verification of the address -- with the password the administrator just
chose.

The platform operator can opt out of that flow (`admin_mode='owner'`): they
set the password themselves and `provision_tenant` creates the OWNER account
immediately. Both paths are deliberate; neither leaves a half-created
account behind.

FAILURE POLICY
--------------
`send_invitation` returns False when SMTP refuses or the template is
unusable; it never raises, because the tenant itself is already committed
and archiving it over a mail server hiccup would be worse than an operator
clicking "resend". The opposite direction -- acceptance -- raises nothing
either: every rejected link is a typed service_response with a status code
the accept page can render.
"""
import json
import logging
import secrets
from datetime import timedelta
from html import escape as _html_escape

from flask import has_request_context, request
from sqlalchemy.exc import IntegrityError

from src.api.extensions import bcrypt
from src.api.models.audit_log_model import AuditLog
from src.api.models.role_model import Role
from src.api.models.tenant_invitation_model import TenantAdminInvitation
from src.api.models.tenant_model import Tenant
from src.api.models.user_model import User
from src.api.tenancy.context import tenant_scope
from src.api.services.template_resolver import TemplateResolver
from src.api.utils.datetime_helper import utcnow
from src.api.utils.email_helper import send_email
from src.api.utils.responses import service_response
from src.api.utils.security import hash_value
from src.api.utils.tenant_urls import tenant_accept_url
from src.api.utils.template_codes import TemplateCode, TemplateVariable
from src.config import get_config


logger = logging.getLogger(__name__)

## Long enough that a hotel setting up its platform account is not racing a
## clock, short enough that a link sitting in an inbox is not a standing
## credential. Seventy-two hours, referenced by the template copy too (the
## EXPIRY_HOURS variable).
INVITATION_EXPIRY_HOURS = 72


## The four faces an invitation presents. Derived from the columns rather
## than stored, so status can never disagree with what accept actually
## enforces -- the same reasoning as `_status_of` in tenant management.
PENDING = "pending"
ACCEPTED = "accepted"
EXPIRED = "expired"
REVOKED = "revoked"


def status_of(invitation: TenantAdminInvitation) -> str:
    if invitation.accepted_at is not None:
        return ACCEPTED
    if invitation.is_deleted:
        return REVOKED
    if invitation.expires_at <= utcnow():
        return EXPIRED
    return PENDING


def create_invitation(db, tenant: Tenant, admin: dict, invited_by: str | None = None) -> dict:
    """Mint a single-use invitation for `tenant` and persist it.

    Shared by the provisioning seeder (a brand-new tenant) and by resend
    (an existing one), so "how an invitation row comes to exist" is defined
    once. Supersedes every earlier live invitation for the tenant first:
    two outstanding links for one administrator is two chances to leak,
    and the older one becoming dead on reissue is the behaviour an operator
    expects when they click resend.

    Returns plain values, not the ORM row: the caller is often a seeder
    that will `db_session.remove()` on the way out, and a detached
    instance's lazy refresh is a trap. The raw token is in this return
    value and nowhere else -- it is not recoverable from the database.
    """
    ## Live = not superseded and not yet accepted. An accepted row is left
    ## alone: it is the historical record that the account was claimed.
    outstanding = (
        db.query(TenantAdminInvitation)
        .filter(
            TenantAdminInvitation.tenant_id == tenant.id,
            TenantAdminInvitation.is_deleted == False,
            TenantAdminInvitation.accepted_at == None,
        )
        .all()
    )
    for row in outstanding:
        ## `deleted_at` is stamped by the shared base_events listener.
        row.is_deleted = True

    raw_token = secrets.token_urlsafe(32)
    invitation = TenantAdminInvitation(
        tenant_id=tenant.id,
        first_name=admin["first_name"],
        last_name=admin["last_name"],
        email=admin["email"],
        token_hash=hash_value(raw_token),
        ## Naive UTC: MySQL DATETIME drops the offset, and every later
        ## comparison reads it back naive (src/api/utils/datetime_helper).
        expires_at=utcnow() + timedelta(hours=INVITATION_EXPIRY_HOURS),
        invited_by=invited_by,
    )
    db.add(invitation)
    db.flush()

    invitation_id = invitation.id
    expires_at = invitation.expires_at
    db.commit()

    return {
        "invitation_id": invitation_id,
        "token": raw_token,
        "expires_at": expires_at,
        "email": admin["email"],
    }


class TenantInvitationService:
    def __init__(self, db):
        self.db = db

    ## ---------------------------------------------------------------- send

    def send_invitation(self, tenant: Tenant, invitation_id: int, raw_token: str) -> bool:
        """Email the accept link for one invitation. Returns SMTP's answer.

        Re-queries the row by id rather than taking an ORM instance from the
        caller: provisioning runs in a seeder session that may already have
        been removed, and the canonical recipient is the row, not a stale
        copy of it.
        """
        invitation = (
            self.db.query(TenantAdminInvitation)
            .filter(
                TenantAdminInvitation.id == invitation_id,
                TenantAdminInvitation.tenant_id == tenant.id,
                TenantAdminInvitation.is_deleted == False,
            )
            .first()
        )
        if invitation is None:
            logger.error(
                "Invitation %s for tenant %s vanished before the email could be sent",
                invitation_id, tenant.id,
            )
            return False

        context = {
            TemplateVariable.USER_NAME.value: f"{invitation.first_name} {invitation.last_name}",
            TemplateVariable.HOTEL_NAME.value: tenant.name,
            TemplateVariable.INVITE_URL.value: tenant_accept_url(
                get_config().PUBLIC_BASE_URL, tenant.slug, raw_token
            ),
            TemplateVariable.EXPIRY_HOURS.value: INVITATION_EXPIRY_HOURS,
        }

        ## Inside the tenant's scope, deliberately: `message_templates` is
        ## tenant-scoped, and this send runs on a platform request with no
        ## tenant bound -- without the scope the resolver would read some
        ## OTHER tenant's copy of the template (or none). Same reasoning as
        ## provision_tenant's scope, applied to a read instead of a write.
        try:
            with tenant_scope(tenant.id, tenant.timezone):
                rendered = TemplateResolver(self.db).render_email(
                    TemplateCode.TENANT_ADMIN_INVITATION.value, context
                )
        except Exception:
            logger.exception(
                "Invitation template resolution raised for tenant %s", tenant.id
            )
            rendered = None

        ## A fallback render has no accept link in it -- the generic copy
        ## talks about a notification, not an invitation -- so sending it
        ## would deliver a click that goes nowhere. The built-in copy below
        ## carries the link and keeps onboarding moving; the ERROR log is
        ## the signal to repair the template row.
        if rendered is None or rendered.get("is_fallback"):
            logger.error(
                "Invitation email for tenant %s using BUILT-IN fallback copy "
                "(template_code='%s'). Check the message_templates row for this "
                "tenant.", tenant.id, TemplateCode.TENANT_ADMIN_INVITATION.value,
            )
        elif rendered.get("missing_variables"):
            logger.warning(
                "Invitation email for tenant %s rendered with unfilled variable(s): %s",
                tenant.id, ", ".join(rendered["missing_variables"]),
            )

        subject, html_body = _invitation_copy(rendered, tenant, context)
        return send_email(invitation.email, subject, html_body)

    ## --------------------------------------------------------------- resend

    def resend(self, tenant: Tenant, actor) -> tuple[dict, int]:
        """Issue a fresh invitation for the tenant's not-yet-claimed admin.

        The invited person's details come from the previous invitation --
        there is nowhere else they could come from at this point: the whole
        premise is that no `users` row exists yet. An already-accepted
        tenant therefore has nothing to resend, and says so.
        """
        latest = (
            self.db.query(TenantAdminInvitation)
            .filter(TenantAdminInvitation.tenant_id == tenant.id)
            .order_by(TenantAdminInvitation.id.desc())
            .first()
        )
        if latest is None:
            return service_response(
                False,
                "This tenant has no administrator invitation on record, so "
                "there is nobody to resend it to. The administrator account "
                "may already have been created another way.",
                None,
                400,
            )
        if latest.accepted_at is not None:
            return service_response(
                False,
                "This tenant's administrator has already accepted their "
                "invitation. Use the user management screen instead.",
                None,
                400,
            )

        admin = {
            "first_name": latest.first_name,
            "last_name": latest.last_name,
            "email": latest.email,
        }
        issued = create_invitation(
            self.db, tenant, admin, invited_by=getattr(actor, "email", None)
        )
        email_sent = self.send_invitation(
            tenant, issued["invitation_id"], issued["token"]
        )

        self._audit(
            actor,
            "RESEND_ADMIN_INVITATION",
            tenant.id,
            {
                "slug": tenant.slug,
                "admin_email": issued["email"],
                "email_sent": email_sent,
            },
        )

        message = (
            f"A new invitation was emailed to {issued['email']}. The previous "
            "link no longer works."
            if email_sent
            else f"The invitation could not be emailed to {issued['email']}. "
                 "Check the mail configuration and resend again."
        )
        return service_response(
            True,
            message,
            {
                "invitation": _serialize(
                    self.db.query(TenantAdminInvitation)
                    .filter(TenantAdminInvitation.id == issued["invitation_id"])
                    .first()
                ),
                "email_sent": email_sent,
            },
            200,
        )

    ## ---------------------------------------------------------- public read

    def latest_for_tenant(self, tenant_id: int) -> dict | None:
        """The tenant's newest invitation, as the console displays it.

        None when the tenant has never had one (created before invitations
        existed, or seeded). Drives the edit screen's resend card: the UI
        shows it only when there IS a record, so it never offers a resend
        the backend would answer 400 to.
        """
        invitation = (
            self.db.query(TenantAdminInvitation)
            .filter(TenantAdminInvitation.tenant_id == tenant_id)
            .order_by(TenantAdminInvitation.id.desc())
            .first()
        )
        return _serialize(invitation)

    def preview(self, token: str) -> tuple[dict, int]:
        """What the accept page needs before asking for a password.

        An unknown token is a 404 and nothing else: no hotel name, no
        status -- the token is the only authorization this endpoint has, so
        it must not confirm that a guess exists. A KNOWN token gets the
        full story, including a revoked one, because the person holding it
        was genuinely invited and deserves "that link was replaced" rather
        than a bare failure.
        """
        invitation = self._by_token(token)
        if invitation is None:
            return service_response(False, "This invitation link is not valid.", None, 404)

        tenant = (
            self.db.query(Tenant).filter(Tenant.id == invitation.tenant_id).first()
        )
        data = _serialize(invitation)
        if tenant is not None:
            data["hotel_name"] = tenant.name
            data["hotel_slug"] = tenant.slug
        return service_response(True, "Invitation fetched successfully.", data, 200)

    ## ------------------------------------------------------ public acceptance

    def accept(self, token: str, password: str) -> tuple[dict, int]:
        """Verify the link, set the password, create the account. One commit."""
        invitation = self._by_token(token)
        if invitation is None:
            return service_response(False, "This invitation link is not valid.", None, 404)

        ## Ordered by how much of the request's own story it tells: a
        ## superseded link is the most common failure (resend happened
        ## after the email arrived), an already-accepted one means the
        ## page should offer login, and expiry is a plain deadline.
        if invitation.is_deleted:
            return service_response(
                False,
                "This invitation link has been replaced by a newer one. "
                "Open the most recent invitation email.",
                None,
                410,
            )
        if invitation.accepted_at is not None:
            return service_response(
                False,
                "This invitation has already been accepted. Sign in instead.",
                None,
                409,
            )
        if invitation.expires_at <= utcnow():
            return service_response(
                False,
                "This invitation link has expired. Ask the platform "
                "administrator to resend it.",
                None,
                410,
            )

        tenant = (
            self.db.query(Tenant).filter(Tenant.id == invitation.tenant_id).first()
        )
        if tenant is None or tenant.is_deleted:
            return service_response(
                False, "This hotel's workspace is no longer available.", None, 410
            )
        if not tenant.is_active:
            ## Deactivating a tenant stops every login (`auth_middleware`
            ## re-checks liveness per request), so letting the account be
            ## created here would only produce a credential that works
            ## nowhere. The invitation stays valid until the tenant is
            ## reactivated.
            return service_response(
                False,
                "This hotel's workspace is temporarily deactivated. Sign-in "
                "will work once it is reactivated.",
                None,
                403,
            )

        ## Direct-owner tenants have no invitation to accept (the account was
        ## created by the platform operator). Accepting their link is meaningless
        ## and would also race a pre-existing user; the message points them to
        ## sign in instead of inventing an error.
        try:
            with tenant_scope(tenant.id, tenant.timezone):
                existing = (
                    self.db.query(User)
                    .filter(
                        User.tenant_id == tenant.id,
                        User.email == invitation.email,
                        User.is_deleted == False,
                    )
                    .first()
                )
                if existing is not None:
                    return service_response(
                        False,
                        "An account with this email already exists for this "
                        "hotel. Sign in instead.",
                        None,
                        409,
                    )
        except Exception:
            ## If the scope read fails for any reason, fall through to the
            ## existing creation path below -- the unique constraint will
            ## catch a real race and the normal errors still apply.
            pass

        hashed = bcrypt.generate_password_hash(password, 12).decode("utf-8")

        ## Tenant scope for the user/role half: `roles` and `users` are
        ## tenant-scoped, and this public endpoint has no tenant bound --
        ## exactly the hole `filters.py` documents for unauthenticated
        ## routes. The scope also stamps nothing implicitly: the user is
        ## given `tenant_id` explicitly, like the seeder's did.
        try:
            with tenant_scope(tenant.id, tenant.timezone):
                existing = (
                    self.db.query(User)
                    .filter(
                        User.tenant_id == tenant.id,
                        User.email == invitation.email,
                        User.is_deleted == False,
                    )
                    .first()
                )
                if existing is not None:
                    return service_response(
                        False,
                        "An account with this email already exists for this "
                        "hotel. Sign in instead.",
                        None,
                        409,
                    )

                ## Resolved by CODE, not id -- ids differ per tenant, and a
                ## literal `1` would mean Owner on one deployment and
                ## Dashboard on another. seed_roles ran during provisioning;
                ## its absence is a seeding failure, not a user error.
                role = (
                    self.db.query(Role)
                    .filter_by(role_code="ADMIN", is_deleted=False)
                    .first()
                )
                if role is None:
                    logger.error(
                        "ADMIN role missing for tenant %s; refusing invitation %s",
                        tenant.id, invitation.id,
                    )
                    return service_response(
                        False,
                        "The hotel's roles are not set up correctly, so the "
                        "account cannot be created. Contact support.",
                        None,
                        500,
                    )

                self.db.add(User(
                    first_name=invitation.first_name,
                    last_name=invitation.last_name,
                    email=invitation.email,
                    password=hashed,
                    role_id=role.id,
                    ## The click through the emailed link is what verified
                    ## this address; the account starts active because it
                    ## was invited, not self-registered.
                    is_email_verified=True,
                    is_active=True,
                    last_password_update_at=utcnow(),
                    tenant_id=tenant.id,
                ))

                ## Same transaction as the insert above: the account either
                ## exists and the token is spent, or neither happened. The
                ## (tenant_id, email) unique constraint is what closes the
                ## concurrent-accept race -- the loser gets IntegrityError
                ## below rather than a second admin.
                invitation.accepted_at = utcnow()

                self.db.add(AuditLog(
                    super_admin_id=None,
                    actor_email=invitation.email,
                    action="ACCEPT_ADMIN_INVITATION",
                    entity_type="tenant",
                    entity_id=tenant.id,
                    details=json.dumps({"slug": tenant.slug}, default=str),
                    ip_address=_client_ip(),
                ))
                self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return service_response(
                False,
                "This invitation has already been accepted. Sign in instead.",
                None,
                409,
            )

        logger.info(
            "Invitation %s accepted; admin %s created for tenant %s",
            invitation.id, invitation.email, tenant.id,
        )
        return service_response(
            True,
            "Your administrator account is ready. Sign in to get started.",
            {
                "email": invitation.email,
                "hotel_name": tenant.name,
                "hotel_slug": tenant.slug,
            },
            200,
        )

    ## -------------------------------------------------------------- helpers

    def _by_token(self, token: str) -> TenantAdminInvitation | None:
        ## Lookup by HASH, so the raw token is never used in a WHERE clause
        ## and never round-trips through a query log.
        return (
            self.db.query(TenantAdminInvitation)
            .filter(TenantAdminInvitation.token_hash == hash_value(token))
            .first()
        )

    def _audit(self, actor, action: str, tenant_id: int, details: dict) -> None:
        """Record a platform-side invitation event. Never fails the operation:
        a missing audit row is a diagnostic gap, a failed resend is not."""
        try:
            self.db.add(AuditLog(
                super_admin_id=getattr(actor, "id", None),
                actor_email=getattr(actor, "email", None),
                action=action,
                entity_type="tenant",
                entity_id=tenant_id,
                details=json.dumps(details, default=str) if details else None,
                ip_address=_client_ip(),
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to write audit log for %s on tenant %s", action, tenant_id)


def _client_ip():
    if not has_request_context():
        return None
    return request.remote_addr


def _invitation_copy(rendered: dict | None, tenant: Tenant, context: dict) -> tuple[str, str]:
    """Subject + HTML body, preferring the tenant's template.

    Falls back to built-in copy when the template row is missing, inactive,
    or unrenderable -- see send_invitation for why fallback copy must carry
    the link itself.
    """
    if rendered and not rendered.get("is_fallback") and rendered.get("html_body"):
        return rendered.get("subject") or "Set up your administrator account", rendered["html_body"]

    subject = f"Set up the administrator account for {tenant.name}"
    body = (
        '<h2 style="color:#333;">Set up the administrator account for '
        f"{_escape(tenant.name)}</h2>"
        f"<p>Hello {_escape(context[TemplateVariable.USER_NAME.value])},</p>"
        "<p>A workspace has been created and you have been invited to be its "
        "administrator. Choose your password to activate the account:</p>"
        f'<p><a href="{_escape(context[TemplateVariable.INVITE_URL.value])}">'
        "Accept invitation</a></p>"
        f"<p>Or copy this link into your browser:</p>"
        f'<p style="word-break:break-all;">'
        f"{_escape(context[TemplateVariable.INVITE_URL.value])}</p>"
        f"<p>This invitation is valid for "
        f"<b>{INVITATION_EXPIRY_HOURS} hours</b>.</p>"
        "<p>If you were not expecting this email, you can safely ignore it.</p>"
        "<br><p>Regards,<br><b>CMS</b></p>"
    )
    return subject, body


def _escape(value) -> str:
    ## The token is URL-safe base64 and the name is the operator's own
    ## input, but the two characters that matter in an href or HTML text
    ## context are escaped regardless -- cheap, and this copy is the one
    ## path that runs when the template layer could not be trusted to.
    return _html_escape(str(value), quote=True)


def _serialize(invitation: TenantAdminInvitation | None) -> dict | None:
    if invitation is None:
        return None
    return {
        "id": invitation.id,
        "first_name": invitation.first_name,
        "last_name": invitation.last_name,
        "email": invitation.email,
        ## Derived, not stored -- see status_of.
        "status": status_of(invitation),
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
        "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
        "invited_by": invitation.invited_by,
        "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
    }
