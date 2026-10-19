"""Platform (super admin) authentication.

This is a second, deliberately separate authentication path from
`auth_middleware.authenticate`. The tenant path resolves a hotel from the URL
or the X-Tenant header and confines every query to it; a platform admin manages
those hotels, so it must run with no tenant at all. Sharing one middleware would
mean teaching the tenant path about a principal that has no tenant, which is
precisely the guarantee that path exists to provide.

Three rules make the separation real rather than cosmetic:

  * Platform tokens are signed with **PLATFORM_JWT_SECRET_KEY**, a different key
    from the tenant `JWT_SECRET_KEY`. A hotel token therefore fails signature
    verification here, and a platform token fails it on a hotel route.
  * A platform token carries `scope: "super_admin"`; a tenant token carries no
    `scope` at all, so this guard refuses it at the scope check below.
  * A platform token carries no `user_id`, so `auth_middleware.authenticate`
    refuses it at its own "Invalid token payload" check.

So neither side can be talked into accepting the other's credentials. The
platform token is additionally bound to a server-side row in
`super_admin_tokens`, which is what makes logout real: revoking that row kills
the token everywhere, not just in the browser that asked.

Nothing here sets a tenant, and nothing here may: the request goes on to touch
only global tables (`tenants`, `super_admin_users`, `audit_logs`), except for
the one scoped block `tenant_management_service` opens explicitly when
provisioning a new hotel or syncing its currency setting.
"""
import logging
from functools import wraps

import jwt
from flask import current_app, g, request
from sqlalchemy import select

from src.api.models.super_admin_token_model import SuperAdminToken
from src.api.models.super_admin_user_model import SuperAdminUser
from src.api.utils.errors import UnauthorizedError
from src.database.session import db_session


## The single marker that separates a platform token from a tenant token. Both
## guards read this one constant rather than spelling a literal each.
SUPER_ADMIN_SCOPE = "super_admin"

## Minted by login when MFA is on, and accepted only by `/auth/verify-mfa`.
## Distinct from the tenant login's `mfa_pending` scope so the two temporary
## tokens can never be replayed against the other's verify endpoint.
SUPER_ADMIN_MFA_PENDING_SCOPE = "super_admin_mfa_pending"


def super_admin_secret() -> str:
    """The platform signing key, or a loud failure if it is not configured.

    Missing configuration must not degrade into "any token is fine". Refusing
    every platform call is the safe direction, and a 500 names the missing key
    rather than silently locking the operator out.
    """
    secret = current_app.config.get("PLATFORM_JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "PLATFORM_JWT_SECRET_KEY is not set, so platform routes are "
            "disabled. Set it in .env; see docs/multi-tenancy.md section 6.3."
        )
    return secret


def authenticate_super_admin():
    """Validate the bearer token and return the platform admin.

    Raises UnauthorizedError (401) for anything that makes the token unusable,
    with the same wording style as the tenant path so a client sees a normal
    auth failure rather than a stack trace.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Authorization token missing")

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            super_admin_secret(),
            algorithms=[current_app.config["PLATFORM_JWT_ALGORITHM"]],
        )

        ## This is the whole tenant-token rejection. A tenant JWT carries no
        ## `scope` claim, so it stops here.
        if payload.get("scope") != SUPER_ADMIN_SCOPE:
            raise UnauthorizedError("Not a platform administrator token")

        ## `sub` is minted as a string (the RFC 7519 subject claim is a string)
        ## and parsed back, rather than trusting PyJWT's handling of a non-string
        ## subject.
        subject = payload.get("sub")
        if not subject:
            raise UnauthorizedError("Invalid token payload")
        try:
            super_admin_id = int(subject)
        except (TypeError, ValueError):
            raise UnauthorizedError("Invalid token payload")

        ## The user row is the authority, exactly as on the tenant path. The
        ## table is global, so the tenant filter never touches this lookup.
        admin = db_session.execute(
            select(SuperAdminUser).filter_by(id=super_admin_id, is_deleted=False)
        ).scalar_one_or_none()
        if not admin:
            raise UnauthorizedError("Super administrator not found")
        if not admin.is_active:
            raise UnauthorizedError("Super administrator account is deactivated")

        ## Revocation. Without this row check a logout only removed the copy the
        ## browser held, and a copied bearer token stayed live until it expired
        ## on its own. `super_admin_tokens` is what logout writes.
        live = db_session.execute(
            select(SuperAdminToken.id).filter(
                SuperAdminToken.super_admin_id == super_admin_id,
                SuperAdminToken.access_token == token,
                SuperAdminToken.is_revoked == False,
            ).limit(1)
        ).first()
        if live is None:
            raise UnauthorizedError("Token has been revoked")

        ## Not a tenant, and none is set: see the module docstring.
        g.current_super_admin = admin
        return admin

    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")
    except UnauthorizedError:
        ## Re-raised unchanged. The blanket `except Exception` below would
        ## otherwise rewrite each of these into a generic auth failure, losing
        ## the reason a call was turned away.
        raise
    except Exception as exc:
        logging.error("Platform authentication failed: %s", exc)
        raise UnauthorizedError("Authorization failed")


def requires_super_admin(f):
    """Wrap a view so it only runs for a valid platform admin.

    Deliberately shares no module/marker system with
    `authorization.requires_module`: that one resolves grants from
    `role_module_access`, which is per-tenant, and a platform admin has no
    hotel's role. Membership in `super_admin_users` *is* the grant here, which is
    why every management endpoint carries this and nothing else.

    No `__required_module__` / `__auth_only__` marker is set: those mark a
    tenant-module contract that this view does not participate in, and setting
    either would mis-report it in scripts/audit_authorization.py.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticate_super_admin()
        return f(*args, **kwargs)

    return decorated
