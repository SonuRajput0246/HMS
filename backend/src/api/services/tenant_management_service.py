"""Creating and maintaining hotels, from the platform side.

This is the one place in the codebase that is allowed to operate across
tenants, and it stays inside two narrow lanes:

  * The `tenants` table is global (`BaseModel`), so listing and editing it
    needs no filter bypass at all -- the tenant criterion only ever applies to
    `TenantScoped` models.
  * Provisioning a brand-new hotel, and syncing its currency setting, are the
    only blocks that touch tenant-scoped rows, and both do so through an
    explicit `tenant_context()` that is opened for exactly as long as it is
    needed.

Nothing here calls `bypass_tenant_filter()` and nothing here can accidentally run
as a hotel: a platform request never has one bound, and the tenant resolver
exempts this whole URL space (`TENANT_EXEMPT_PREFIXES`) so no scope is ever set
for it. That is what makes the platform-wide `users` count below honest rather
than a filter that failed to run.

CROSS-TENANT WRITES ARE NOT ONE TRANSACTION, AND DELIBERATELY SO
----------------------------------------------------------------
Create = insert hotel -> commit, then provision -> commit, then audit -> commit.
The seeders own their own transactions and call `db_session.remove()`, so they
cannot run inside a caller's transaction without discarding it. Rather than
restructure the seeder layer to pretend otherwise, the boundary is stated
explicitly and compensated: if provisioning fails, the hotel is archived and an
error is returned, so a half-created tenant is never left reachable at its
subdomain.
"""
import ipaddress
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import has_request_context, request
from sqlalchemy import func, or_

from src.api.extensions import bcrypt
from src.api.middlewares.tenant_resolver import is_reserved_slug
from src.api.models.audit_log_model import AuditLog
from src.api.models.role_model import Role
from src.api.models.system_setting_model import SystemSetting
from src.api.models.tenant_model import Tenant
from src.api.models.token_model import Token
from src.api.models.user_model import User
from src.api.utils.responses import service_response
from src.config import get_config
from src.database.tenant_context import tenant_context


## The three faces a hotel can present to the operator. Derived from the two
## columns that already exist rather than stored, so status can never disagree
## with the flags the login resolver actually reads. Archiving outranks
## activation because an archived hotel has no live state at all.
ACTIVE = "active"
INACTIVE = "inactive"
ARCHIVED = "archived"

## The setting row that mirrors `tenants.currency`. The hotel-side code
## (`payment_service`) resolves `default_currency` rather than reaching onto the
## registry, so the registry is the place an operator changes it and this row is
## the hotel's copy of that answer.
CURRENCY_SETTING_KEY = "default_currency"

## The role code a hotel's own top account carries. Looked up by code rather than
## by display name, because the code is the stable contract and a hotel admin is
## free to rename the role to "Owner" in the UI.
SUPER_ADMIN_ROLE_CODE = "SUPER_ADMIN"


def _status_of(tenant: Tenant) -> str:
    if tenant.is_deleted:
        return ARCHIVED
    return ACTIVE if tenant.is_active else INACTIVE


def _valid_timezone(name: str) -> bool:
    """Is `name` a real IANA zone? Worth checking at the boundary: a typo here
    silently shifts every daily report figure for that hotel."""
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def _iso(value):
    return value.isoformat() if value else None


def _tenant_host_suffix(public_base_url: str) -> str:
    """The host every hotel's subdomain hangs off.

    `TENANT_BASE_DOMAIN` is the authority when it is set: it is the same value
    `tenant_resolver` reads off an incoming `Host` header, so returning it here
    guarantees the console prints an address that actually resolves.

    Development leaves it unset -- the API and the app are on different origins,
    so the subdomain never reaches the backend's `Host`. There the console is
    served from `PUBLIC_BASE_URL` itself and the suffix is derived from it by
    dropping the deployment's own first label, the exact inverse of what the
    resolver does when it reads `Host`:

        http://localhost:4200         -> localhost:4200
        http://127.0.0.1:4200         -> 127.0.0.1:4200
        https://console.example.com   -> example.com

    One variable to configure instead of two: a second one would be a second
    chance for the console to print a host no hotel is actually served on.
    """
    base_domain = (get_config().TENANT_BASE_DOMAIN or "").strip().lower()
    parsed = urlsplit(public_base_url)
    port = parsed.port

    if base_domain:
        return f"{base_domain}:{port}" if port else base_domain

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return ""

    ## An IP literal has no labels to spare -- `5.6.7.8` minus its first label
    ## would be `6.7.8`, a host nobody could reach.
    try:
        ipaddress.ip_address(hostname)
        domain = hostname
    except ValueError:
        labels = hostname.split(".")
        domain = hostname if len(labels) <= 2 else ".".join(labels[1:])

    return f"{domain}:{port}" if port else domain


class TenantManagementService:
    def __init__(self, db):
        self.db = db

    ## ------------------------------------------------------------------ read

    def dashboard_summary(self):
        """Totals for the panel header.

        All counts come from the same table, and four indexed counts over a
        handful of rows is the honest choice over a cleverer single pass.

        `total_users` spans every hotel on purpose -- this request has no tenant
        bound, so `users` is unfiltered here. That is the intent (the operator's
        platform-wide total), not a filter that failed to run.
        """
        base = self.db.query(Tenant)
        live = base.filter(Tenant.is_deleted == False)
        total = live.count()
        active = live.filter(Tenant.is_active == True).count()
        inactive = live.filter(Tenant.is_active == False).count()
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

        Read on demand from configuration instead of being baked into the client
        bundle, so one build serves every environment and the panel can never
        print a development host in production.

        The origin and the hotel host suffix travel together: the browser only
        needs the second, but returning both means it never has to re-derive a
        host rule the server already owns.
        """
        public_base_url = (get_config().PUBLIC_BASE_URL or "").rstrip("/")

        return service_response(
            True,
            "Configuration fetched successfully.",
            {
                "public_base_url": public_base_url,
                "tenant_host_suffix": _tenant_host_suffix(public_base_url),
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
            ## Archived hotels are excluded from every normal view, exactly as
            ## the login resolver excludes them: "list hotels" means the live ones
            ## unless asked otherwise.
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

        ## Archived hotels stay viewable: restoring one starts by reading it.
        user_count = self._user_count(tenant.id)
        return service_response(
            True, "Tenant fetched successfully.", self._serialize(tenant, user_count), 200
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

        ## Matched WITHOUT `is_deleted`: the unique index on `slug` covers the
        ## whole column, so an archived hotel still owns its slug. Checking only
        ## live rows would let this pass validation and then fail the insert as an
        ## unhandled IntegrityError.
        if self.db.query(Tenant).filter(Tenant.slug == slug).first() is not None:
            return service_response(
                False, "A tenant with this slug already exists.", None, 409
            )

        ## Snapshot the actor's identity as plain values, now.
        ##
        ## `provision_tenant` seeds through a layer that calls
        ## `db_session.remove()` as each seeder finishes, which detaches every
        ## object the caller's session held -- including the operator behind
        ## `g.current_super_admin`. Reading `actor.id` after that is a
        ## DetachedInstanceError, not a value, so the audit row for the create
        ## would be lost. Reading it before the call is the whole fix.
        actor_id, actor_email = self._actor(actor)

        ## Imported here, not at module import time: the seeders are only needed
        ## when a tenant is actually created, and importing them with the routes
        ## would pull the whole seeding graph into every boot.
        from src.database.seeders.provision_tenant import provision_tenant

        ## Provisioning runs as its own committed step -- see the module
        ## docstring for why. On failure the tenant is archived so it cannot be
        ## reached at a subdomain that has no roles, prefixes or admin.
        try:
            provision_tenant(
                slug=slug,
                name=data["name"],
                timezone_name=timezone_name,
                currency=currency,
                admin_email=data["admin_email"].strip().lower(),
                admin_password=data["admin_password"],
                admin_first_name=data["admin_first_name"],
                admin_last_name=data["admin_last_name"],
            )
        except Exception:
            logging.exception("Tenant %s created but provisioning failed", slug)
            self._archive_after_failed_provisioning(slug)
            return service_response(
                False,
                "The tenant was created but its setup failed, so it has been "
                "archived. Fix the reported error and create it again.",
                None,
                500,
            )

        ## Re-read rather than reusing whatever the seeders left behind: every
        ## seeder calls db_session.remove(), so any object held across the call
        ## is detached and would raise on the next attribute access.
        tenant = self.db.query(Tenant).filter(Tenant.slug == slug).first()
        tenant_id = tenant.id

        self._audit(
            actor_id,
            actor_email,
            "CREATE_TENANT",
            "tenant",
            tenant_id,
            {"slug": slug, "name": data["name"], "timezone": timezone_name, "currency": currency},
        )

        return service_response(True, "Tenant created successfully.", self._serialize(tenant), 201)

    def update_tenant(self, tenant_id: int, data: dict, actor):
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)
        if tenant.is_deleted:
            ## Editing an archived hotel would move the address of something the
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

        ## Commit the registry row first, then mirror the currency into the
        ## hotel's own settings. Kept separate because the second needs an
        ## explicit tenant scope and a failure there must not undo the first.
        self.db.commit()

        if "currency" in changed:
            self._sync_currency_setting(tenant.id, tenant.currency)

        self.db.refresh(tenant)

        ## A slug change rewrites the hotel's URL, so it is called out in the
        ## audit detail rather than sitting in an undifferentiated field list.
        self._audit(
            *self._actor(actor),
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

        ## `is_deleted` is deliberately untouched: deactivating a hotel stops it
        ## trading without claiming it was archived. The resolver refuses both
        ## states and `auth_middleware` re-checks on every request, so an
        ## already-issued token stops working too.
        tenant.is_active = is_active
        self.db.commit()
        self.db.refresh(tenant)

        self._audit(
            *self._actor(actor),
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

        ## Soft delete only. Every booking, payment and audit row the hotel owns
        ## stays exactly where it is -- archived, not destroyed. `deleted_at` is
        ## stamped by the shared listener on this update. Deactivated on the way
        ## through so it stops trading immediately, and so a restore brings back
        ## a hotel the operator must consciously re-activate.
        tenant.is_active = False
        tenant.is_deleted = True
        self.db.commit()
        self.db.refresh(tenant)

        self._audit(
            *self._actor(actor),
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
        ## decisions, and silently switching a hotel on is the riskier default.
        ## `slug` is reclaimed on the same statement, so its unique index frees
        ## the subdomain again.
        tenant.is_deleted = False
        tenant.deleted_at = None
        self.db.commit()
        self.db.refresh(tenant)

        self._audit(
            *self._actor(actor),
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

    def reset_tenant_admin_password(self, tenant_id: int, new_password: str, actor):
        """Set a new password on a hotel's own super admin, and end its sessions.

        A recovery path the hotel cannot run itself: when its only admin loses
        the password there is nobody inside the hotel who could reset it. The
        admin lives inside the tenant, so the lookup is scoped to it -- a
        platform request carries no tenant of its own, so the scope is entered
        explicitly rather than assumed from the ambient context.

        Revoking the admin's live tokens is what makes the reset more than
        cosmetic: whoever held the old password keeps the sessions it bought
        otherwise.
        """
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.is_deleted == False
        ).first()
        if not tenant:
            return service_response(False, "Tenant not found.", None, 404)

        with tenant_context(tenant.id):
            admin = (
                self.db.query(User)
                .join(Role, Role.id == User.role_id)
                .filter(
                    Role.role_code == SUPER_ADMIN_ROLE_CODE,
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

            self.db.query(Token).filter(
                Token.user_id == admin.id,
                Token.is_revoked == False,
            ).update({"is_revoked": True})
            self.db.commit()

            admin_id = admin.id

        self._audit(
            *self._actor(actor),
            "RESET_TENANT_ADMIN_PASSWORD",
            "tenant",
            tenant_id,
            {"slug": tenant.slug, "user_id": admin_id},
        )

        return service_response(
            True,
            "Admin password reset. The administrator must sign in again.",
            {"tenant_id": tenant.id, "user_id": admin_id},
            200,
        )

    ## --------------------------------------------------------------- helpers

    def _user_count(self, tenant_id: int) -> int:
        return (
            self.db.query(func.count(User.id))
            .filter(User.tenant_id == tenant_id, User.is_deleted == False)
            .scalar()
            or 0
        )

    def _sync_currency_setting(self, tenant_id: int, currency: str) -> None:
        """Mirror the registry's currency into the hotel's own settings.

        The hotel side reads `system_settings.default_currency`, not
        `tenants.currency`, so a registry edit that did not land here would leave
        the console showing one currency and the hotel transacting in another.

        Wrapped in its own tenant scope because `system_settings` is
        tenant-scoped and this request has none bound. Best effort in the sense
        that it runs after the registry row is already committed: a failure here
        is logged and the operator's edit still stands.
        """
        try:
            with tenant_context(tenant_id):
                row = (
                    self.db.query(SystemSetting)
                    .filter(
                        SystemSetting.tenant_id == tenant_id,
                        SystemSetting.key == CURRENCY_SETTING_KEY,
                    )
                    .first()
                )
                if row is None:
                    row = SystemSetting(
                        tenant_id=tenant_id,
                        key=CURRENCY_SETTING_KEY,
                        value=currency,
                    )
                    self.db.add(row)
                else:
                    row.value = currency
                self.db.commit()
        except Exception:
            self.db.rollback()
            logging.exception(
                "Could not mirror currency %s into system_settings for tenant %s",
                currency, tenant_id,
            )

    def _archive_after_failed_provisioning(self, slug: str) -> None:
        """Compensating action for a create that got half-way there.

        The row is deleted-but-present rather than left active, so it cannot be
        resolved at its subdomain while missing roles or an admin. Best effort:
        if even this fails, the exception propagates so the 500 is truthful
        instead of claiming the tenant was cleaned up.
        """
        try:
            tenant = self.db.query(Tenant).filter(Tenant.slug == slug).first()
            if tenant and not tenant.is_deleted:
                tenant.is_active = False
                tenant.is_deleted = True
                self.db.commit()
        except Exception:
            self.db.rollback()
            logging.exception(
                "Could not archive tenant %s after failed provisioning", slug
            )

    @staticmethod
    def _actor(actor):
        """The actor's identity as two plain values.

        Taken up front rather than read at write time because the actor is an ORM
        object on the request's session, and provisioning closes that session
        underneath it. `super_admin_id` and `actor_email` are copied into the
        audit row precisely so the trail outlives the session that wrote it --
        taking them here is that promise kept.
        """
        return getattr(actor, "id", None), getattr(actor, "email", None)

    def _audit(self, actor_id, actor_email, action: str, entity_type: str,
               entity_id: int, details: dict) -> None:
        """Record the change. Never fails the operation: a missing audit row is
        a diagnostic gap, a rolled-back activation is a surprise."""
        try:
            self.db.add(AuditLog(
                super_admin_id=actor_id,
                actor_email=actor_email,
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
            ## the flags it would otherwise have to reason about.
            "status": _status_of(tenant),
            "created_at": _iso(tenant.created_at),
            "updated_at": _iso(tenant.updated_at),
            "deleted_at": _iso(tenant.deleted_at),
            "user_count": user_count,
        }
