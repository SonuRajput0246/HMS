"""Creating and maintaining tenants, from the platform side.

This is the one place in the codebase that is allowed to operate across
tenants, and it stays inside two narrow lanes:

  * The `tenants` table is global (`BaseModel`), so listing and editing it
    needs no filter bypass at all -- the tenant criterion only ever applies to
    `BaseTenantModel`.
  * Provisioning a brand-new tenant is the sole block that touches
    tenant-scoped rows, and it does so through `provision_tenant()`, which
    opens an explicit `tenant_scope` for exactly as long as it needs one.

Nothing here calls `bypass_tenant_filter()` and nothing here can accidentally
run as a tenant: a platform request never has one bound. If that ever stopped
being true, a tenant-scoped query would return one cafe's rows rather than all
of them -- a leak of *correctness*, never of a tenant's data to the operator
who already owns it.

CROSS-TENANT WRITES ARE NOT ONE TRANSACTION, AND DELIBERATELY SO
---------------------------------------------------------------
Create = insert tenant -> commit, then provision -> commit, then audit -> commit.
The seeders own their own transactions and call `db_session.remove()`, so they
cannot run inside a caller's transaction without discarding it. Rather than
restructure the seeder layer to pretend otherwise, the boundary is stated
explicitly and compensated: if provisioning fails, the tenant is archived and
an error is returned, so a half-created cafe is never left reachable at its
subdomain.
"""
import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import has_request_context, request
from sqlalchemy import func, or_

from src.api.models.audit_log_model import AuditLog
from src.api.models.tenant_model import Tenant
from src.api.models.user_model import User
from src.api.services.tenant_invitation_service import TenantInvitationService
from src.api.tenancy.resolution import is_reserved_slug
from src.api.utils.responses import service_response
from src.api.utils.tenant_urls import tenant_domain as _tenant_domain
from src.config import get_config
from src.database.seeders.tenant_defaults_seeder import provision_tenant


## The three faces a tenant can present to the operator. Derived from the two
## columns that already exist rather than stored, so status can never disagree
## with the flags the login resolver actually reads.
ACTIVE = "active"
INACTIVE = "inactive"
ARCHIVED = "archived"


def _status_of(tenant: Tenant) -> str:
    if tenant.is_deleted:
        return ARCHIVED
    return ACTIVE if tenant.is_active else INACTIVE


def _valid_timezone(name: str) -> bool:
    """Is `name` a real IANA zone? Worth checking at the boundary: a typo here
    silently shifts every daily report figure for that cafe."""
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def _iso(value):
    return value.isoformat() if value else None


class TenantManagementService:
    def __init__(self, db):
        self.db = db
        ## Beside, not inside, this service: issuing and delivering an
        ## invitation is its own lifecycle (issue -> email -> accept), and
        ## create/resend are two entry points onto it.
        self.invitation_service = TenantInvitationService(db)

    ## ------------------------------------------------------------------ read

    def dashboard_summary(self):
        """Totals for the panel header.

        All four counts come from the same table in one pass of groupings via
        conditional aggregates would be cleverer but harder to read; four
        indexed counts over a handful of rows is the honest choice.

        `total_users` spans every tenant on purpose -- this request has none
        bound, so `users` is unfiltered here. That is the intent (the
        operator's platform-wide total), not a filter that failed to run.
        """
        base = self.db.query(Tenant)
        total = base.filter(Tenant.is_deleted == False).count()
        active = base.filter(Tenant.is_deleted == False, Tenant.is_active == True).count()
        inactive = base.filter(Tenant.is_deleted == False, Tenant.is_active == False).count()
        archived = base.filter(Tenant.is_deleted == True).count()
        total_users = self.db.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0

        return service_response(
            True,
            "Summary fetched successfully.",
            {
                "total_tenants": total,
                "active_tenants": active,
                "inactive_tenants": inactive,
                "archived_tenants": archived,
                "total_users": total_users,
            },
            200,
        )

    def platform_config(self):
        """The deployment the console is running against.

        Read on demand from `PUBLIC_BASE_URL` instead of being baked into the
        client bundle, so one build serves every environment and the panel can
        never print a development host in production.

        The origin and the tenant domain beneath it travel together: the
        browser only needs the second, but returning both means it never has to
        re-derive a host rule the server already owns -- and disagrees with
        nobody when they match, which in every sane deployment they do.
        """
        public_base_url = (get_config().PUBLIC_BASE_URL or "").rstrip("/")

        return service_response(
            True,
            "Configuration fetched successfully.",
            {
                "public_base_url": public_base_url,
                "tenant_host_suffix": _tenant_domain(public_base_url),
            },
            200,
        )

    def get_tenants(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = (data.get("search_value") or "").strip()
        status = data.get("status")

        query = self.db.query(Tenant)

        if status == ARCHIVED:
            query = query.filter(Tenant.is_deleted == True)
        else:
            ## Archived tenants are excluded from every normal view, exactly as
            ## the login resolver excludes them: "list tenants" means the live
            ## ones unless asked otherwise.
            query = query.filter(Tenant.is_deleted == False)
            if status == ACTIVE:
                query = query.filter(Tenant.is_active == True)
            elif status == INACTIVE:
                query = query.filter(Tenant.is_active == False)

        if search_value:
            ## Both columns: operators reach for the hotel name, users reach
            ## for the subdomain they type.
            query = query.filter(
                or_(
                    Tenant.name.like(f"%{search_value}%"),
                    Tenant.slug.like(f"%{search_value}%"),
                )
            )

        total_records = query.count()
        tenants = (
            query
            .order_by(Tenant.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        ## One grouped query for the whole page rather than one per row.
        user_counts = {}
        ids = [tenant.id for tenant in tenants]
        if ids:
            user_counts = dict(
                self.db.query(User.tenant_id, func.count(User.id))
                .filter(User.tenant_id.in_(ids), User.is_deleted == False)
                .group_by(User.tenant_id)
                .all()
            )

        last_page = (total_records + page_size - 1) // page_size if total_records > 0 else 1

        return {
            "status": True,
            "data": [self._serialize(t, user_counts.get(t.id, 0)) for t in tenants],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size,
            },
        }, 200

    def get_tenant_by_id(self, tenant_id: int):
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)

        ## Archived tenants stay viewable: restoring one starts by reading it.
        user_count = (
            self.db.query(func.count(User.id))
            .filter(User.tenant_id == tenant.id, User.is_deleted == False)
            .scalar()
            or 0
        )
        payload = self._serialize(tenant, user_count)
        ## The first administrator's invitation rides along so the edit
        ## screen can offer "Resend invitation" exactly when there is a live
        ## record to resend, and stay silent when there is not. None (never
        ## issued) rather than an error: this is a display concern, not a
        ## precondition for reading a tenant.
        payload["admin_invitation"] = self.invitation_service.latest_for_tenant(
            tenant.id
        )
        return service_response(
            True, "Tenant fetched successfully.", payload, 200
        )

    ## ----------------------------------------------------------------- write

    def create_tenant(self, data: dict, actor):
        slug = data["slug"].strip().lower()
        timezone_name = data["timezone"].strip()
        currency = data["currency"].strip().upper()

        if is_reserved_slug(slug):
            return service_response(
                False,
                "That slug is reserved for the platform and cannot be a tenant's address.",
                None,
                400,
            )

        if not _valid_timezone(timezone_name):
            return service_response(
                False,
                f"'{timezone_name}' is not a valid IANA timezone (for example Asia/Kolkata).",
                None,
                400,
            )

        ## Matched WITHOUT `is_deleted`: `ux_tenant_slug` is unique across the
        ## whole column, so an archived tenant still owns its slug. Checking
        ## only live rows would let this pass validation and then fail the
        ## insert as an unhandled IntegrityError.
        if self.db.query(Tenant).filter(Tenant.slug == slug).first() is not None:
            return service_response(
                False, "A tenant with this slug already exists.", None, 409
            )

        tenant = Tenant(
            name=data["name"],
            slug=slug,
            timezone=timezone_name,
            currency=currency,
            is_active=True,
            is_deleted=False,
        )
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        tenant_id = tenant.id

        ## Provisioning runs as its own committed step -- see the module
        ## docstring for why. On failure the tenant is archived so it cannot be
        ## reached at a subdomain that has no roles, prefixes or admin.
        ##
        ## The password is present only when the operator chose to create the
        ## owner directly; `provision_tenant` branches on that and never sees
        ## a credential it should not use.
        try:
            provisioned = provision_tenant(
                tenant_id=tenant_id,
                timezone_name=timezone_name,
                currency=currency,
                admin={
                    "first_name": data["admin_first_name"],
                    "last_name": data["admin_last_name"],
                    "email": data["admin_email"].strip().lower(),
                    "password": data.get("admin_password"),
                },
            )
        except Exception:
            logging.exception("Tenant %s created but provisioning failed", slug)
            self._archive_after_failed_provisioning(tenant_id)
            return service_response(
                False,
                "The tenant was created but its setup failed, so it has been "
                "archived. Fix the reported error and create it again.",
                None,
                500,
            )

        mode = provisioned.get("mode", "invitation")

        ## Delivery is deliberately OUTSIDE the provisioning try: the tenant
        ## and its admin record are committed, and a mail server refusing a
        ## message must not archive a perfectly good cafe. Failure lands in
        ## `email_sent` below, and the operator has Resend invitation. The
        ## direct-owner path has nothing to deliver at all.
        created = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        email_sent = False
        if mode == "invitation":
            try:
                email_sent = self.invitation_service.send_invitation(
                    tenant=created,
                    invitation_id=provisioned["invitation_id"],
                    raw_token=provisioned["token"],
                )
            except Exception:
                logging.exception(
                    "Tenant %s created but the admin invitation email failed", slug
                )

        details = {
            "slug": slug,
            "name": data["name"],
            "timezone": timezone_name,
            "currency": currency,
            "admin_email": provisioned["email"],
            "admin_mode": mode,
        }
        if mode == "invitation":
            ## Part of the record: whether the admin can act on the create
            ## RIGHT NOW depends on this flag, not on the row.
            details["invitation_email_sent"] = email_sent
        self._audit(actor, "CREATE_TENANT", "tenant", tenant_id, details)

        payload = self._serialize(created)
        payload["admin_mode"] = mode
        ## None in owner mode: there is no invitation to resend, and the edit
        ## screen keys the resend card off exactly this value.
        payload["admin_invitation"] = (
            {
                "email": provisioned["email"],
                "expires_at": _iso(provisioned["expires_at"]),
                "email_sent": email_sent,
            }
            if mode == "invitation"
            else None
        )

        if mode == "owner":
            message = (
                f"Tenant created. The owner account for {provisioned['email']} "
                "was created with the password you set."
            )
        elif email_sent:
            message = (
                f"Tenant created. The administrator invitation was emailed to "
                f"{provisioned['email']}."
            )
        elif mode == "invitation":  ## issued, but SMTP refused
            message = (
                f"Tenant created, but the invitation email could not be sent "
                f"to {provisioned['email']}. Use 'Resend invitation' to try again."
            )
        else:  ## pragma: no cover -- provisioning only returns the two modes
            ## above; reaching this would mean the seeder invented a third one.
            message = "Tenant created without an administrator."
        return service_response(True, message, payload, 201)

    def update_tenant(self, tenant_id: int, data: dict, actor):
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)
        if tenant.is_deleted:
            ## Editing an archived cafe would move the address of something the
            ## resolver refuses, which is never what the operator meant.
            return service_response(
                False, "Restore this tenant before editing it.", None, 400
            )

        if not data:
            return service_response(False, "No changes supplied.", None, 400)

        ## Fields are only touched when present, so one screen can submit a
        ## single column and the rest keep their values.
        if "timezone" in data and not _valid_timezone(data["timezone"]):
            return service_response(
                False,
                f"'{data['timezone']}' is not a valid IANA timezone (for example Asia/Kolkata).",
                None,
                400,
            )

        changed = {}

        if "name" in data and data["name"] != tenant.name:
            changed["name"] = {"from": tenant.name, "to": data["name"]}
            tenant.name = data["name"]

        if "timezone" in data and data["timezone"] != tenant.timezone:
            changed["timezone"] = {"from": tenant.timezone, "to": data["timezone"]}
            tenant.timezone = data["timezone"]

        if "currency" in data:
            currency = data["currency"].strip().upper()
            if currency != tenant.currency:
                changed["currency"] = {"from": tenant.currency, "to": currency}
                tenant.currency = currency

        if "slug" in data:
            slug = data["slug"].strip().lower()
            if is_reserved_slug(slug):
                return service_response(
                    False,
                    "That slug is reserved for the platform and cannot be a tenant's address.",
                    None,
                    400,
                )
            if slug != tenant.slug:
                clash = (
                    self.db.query(Tenant)
                    .filter(Tenant.slug == slug, Tenant.id != tenant.id)
                    .first()
                )
                if clash is not None:
                    return service_response(
                        False, "A tenant with this slug already exists.", None, 409
                    )
                changed["slug"] = {"from": tenant.slug, "to": slug}
                tenant.slug = slug

        if not changed:
            return service_response(True, "Nothing changed.", self._serialize(tenant), 200)

        self.db.commit()
        self.db.refresh(tenant)

        ## A slug change rewrites the hotel's URL, so it is called out in the
        ## audit detail rather than sitting in an undifferentiated field list.
        self._audit(
            actor,
            "UPDATE_TENANT",
            "tenant",
            tenant_id,
            {
                "slug": tenant.slug,
                "changed": changed,
                "url_moved": "slug" in changed,
            },
        )

        return service_response(True, "Tenant updated successfully.", self._serialize(tenant), 200)

    def set_tenant_status(self, tenant_id: int, is_active: bool, actor):
        tenant = (
            self.db.query(Tenant)
            .filter(Tenant.id == tenant_id, Tenant.is_deleted == False)
            .first()
        )
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)

        if tenant.is_active == is_active:
            return service_response(True, "Nothing changed.", self._serialize(tenant), 200)

        ## `is_deleted` is deliberately untouched: deactivating a cafe stops it
        ## trading without claiming it was archived. The resolver refuses both
        ## states, and `auth_middleware` re-checks on every request, so an
        ## already-issued token stops working too.
        tenant.is_active = is_active
        self.db.commit()
        self.db.refresh(tenant)

        self._audit(
            actor,
            "ACTIVATE_TENANT" if is_active else "DEACTIVATE_TENANT",
            "tenant",
            tenant_id,
            {"slug": tenant.slug, "is_active": is_active},
        )

        return service_response(
            True,
            "Tenant activated successfully." if is_active else "Tenant deactivated successfully.",
            self._serialize(tenant),
            200,
        )

    def archive_tenant(self, tenant_id: int, actor):
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)
        if tenant.is_deleted:
            return service_response(False, "This tenant is already archived.", None, 400)

        ## Soft delete only. Every order, invoice and audit row the cafe owns
        ## stays exactly where it is -- archived, not destroyed. `deleted_at`
        ## is stamped by the shared base_events listener on this update.
        tenant.is_active = False
        tenant.is_deleted = True
        self.db.commit()
        self.db.refresh(tenant)

        self._audit(
            actor,
            "ARCHIVE_TENANT",
            "tenant",
            tenant_id,
            {"slug": tenant.slug, "name": tenant.name},
        )

        return service_response(
            True, "Tenant archived successfully.", self._serialize(tenant), 200
        )

    def restore_tenant(self, tenant_id: int, actor):
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)
        if not tenant.is_deleted:
            return service_response(False, "This tenant is not archived.", None, 400)

        ## Restored but left INACTIVE: coming back and trading are two separate
        ## decisions, and silently switching a cafe on is the riskier default.
        ## `slug` is reclaimed on the same statement, so its unique index frees
        ## the subdomain again.
        tenant.is_deleted = False
        tenant.deleted_at = None
        self.db.commit()
        self.db.refresh(tenant)

        self._audit(
            actor,
            "RESTORE_TENANT",
            "tenant",
            tenant_id,
            {"slug": tenant.slug, "is_active": tenant.is_active},
        )

        return service_response(
            True,
            "Tenant restored. It is inactive until you activate it.",
            self._serialize(tenant),
            200,
        )

    def resend_admin_invitation(self, tenant_id: int, actor):
        """Re-issue and re-email the tenant's first-administrator invitation.

        Kept here as a thin door onto `TenantInvitationService.resend`: the
        tenant-existence rules are this service's (identical to edit: find
        the row, refuse an archived one), and everything about invitations
        lives in the invitation service.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)
        if tenant.is_deleted:
            return service_response(
                False, "Restore this tenant before resending its invitation.", None, 400
            )

        return self.invitation_service.resend(tenant, actor)

    ## --------------------------------------------------------------- helpers

    def _archive_after_failed_provisioning(self, tenant_id: int) -> None:
        """Compensating action for a create that got half-way there.

        The row is deleted-but-present rather than left active, so it cannot be
        resolved at its subdomain while missing roles or an admin. Best effort:
        if even this fails, the exception propagates so the 500 is truthful
        instead of claiming the tenant was cleaned up.
        """
        try:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant and not tenant.is_deleted:
                tenant.is_active = False
                tenant.is_deleted = True
                self.db.commit()
        except Exception:
            self.db.rollback()
            logging.exception(
                "Could not archive tenant %s after failed provisioning", tenant_id
            )

    def _audit(self, actor, action: str, entity_type: str, entity_id: int, details: dict) -> None:
        """Record the change. Never fails the operation: a missing audit row is
        a diagnostic gap, a rolled-back activation is a surprise."""
        try:
            self.db.add(AuditLog(
                super_admin_id=getattr(actor, "id", None),
                actor_email=getattr(actor, "email", None),
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=json.dumps(details, default=str) if details else None,
                ip_address=self._client_ip(),
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logging.exception("Failed to write audit log for %s on %s %s", action, entity_type, entity_id)

    @staticmethod
    def _client_ip():
        if not has_request_context():
            return None
        return request.remote_addr

    @staticmethod
    def _serialize(tenant: Tenant, user_count: int | None = None) -> dict:
        return {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "timezone": tenant.timezone,
            "currency": tenant.currency,
            "is_active": tenant.is_active,
            "is_deleted": tenant.is_deleted,
            ## Derived, not stored -- see _status_of. Gives the UI one word for
            ## the pair of flags it would otherwise have to reason about.
            "status": _status_of(tenant),
            "created_at": _iso(tenant.created_at),
            "updated_at": _iso(tenant.updated_at),
            "deleted_at": _iso(tenant.deleted_at),
            "user_count": user_count,
        }
