"""Authentication for the platform operator, who sits above every tenant.

A platform user creates and administers hotels. They are not a row in `users`
and they belong to no tenant, so they cannot authenticate through the hotel login
route. Two things keep the two identity systems apart:

  * a **different signing secret** (`PLATFORM_JWT_SECRET_KEY`), so a hotel token
    fails signature verification on a platform route and a platform token fails
    it on a hotel route;
  * a **scope claim** (`scope == "platform"`), checked on the way in, so a token
    that somehow verified against the wrong secret is still refused.

Platform routes live under `/api/v1/platform`, which the tenant resolver is
explicitly exempt for -- there is no hotel to resolve. This module is the gate in
front of them, the platform counterpart of `authenticate()` in auth_middleware.

Tokens are stateless: there is no `platform_tokens` table, so a platform session
cannot be revoked before it expires. Keep the expiry short, and rotate the secret
if that ever becomes a problem.
"""
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from src.api.models.platform_user_model import PlatformUser
from src.api.utils.errors import UnauthorizedError
from src.database.session import db_session

PLATFORM_SCOPE = "platform"


def platform_secret() -> str:
    """The platform signing key, or a loud failure if it is not configured.

    Missing configuration must not degrade into "any token is fine". Refusing
    every platform call is the safe direction, and a 500 names the missing key
    rather than silently locking the operator out.
    """
    secret = current_app.config.get("PLATFORM_JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "PLATFORM_JWT_SECRET_KEY is not set, so platform routes are "
            "disabled. Set it in .env; see docs/multi-tenancy.md §6.3."
        )
    return secret


def mint_platform_token(platform_user) -> str:
    """A signed platform access token for `platform_user`."""
    now = datetime.now(timezone.utc)
    payload = {
        "platform_user_id": platform_user.id,
        "scope": PLATFORM_SCOPE,
        "iat": now,
        "exp": now + timedelta(minutes=current_app.config["PLATFORM_JWT_EXPIRES_MIN"]),
        ## Distinct per issuance, for the same reason the tenant tokens carry one.
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        platform_secret(),
        algorithm=current_app.config["PLATFORM_JWT_ALGORITHM"],
    )


def authenticate_platform():
    """Validate the bearer token and return the platform user.

    Raises UnauthorizedError (401) for anything that makes the token unusable.
    The platform user is not tenant-scoped, so this needs no tenant context.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Authorization token missing")

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            platform_secret(),
            algorithms=[current_app.config["PLATFORM_JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")

    ## The scope guard. A hotel token has no `scope`; a token minted here always
    ## does. Rejecting anything else keeps the two audiences from ever crossing.
    if payload.get("scope") != PLATFORM_SCOPE:
        raise UnauthorizedError("Not a platform token")

    platform_user_id = payload.get("platform_user_id")
    if not platform_user_id:
        raise UnauthorizedError("Invalid token payload")

    platform_user = db_session.get(PlatformUser, platform_user_id)
    if not platform_user or platform_user.is_deleted:
        raise UnauthorizedError("Platform account not found")
    if not platform_user.is_active:
        raise UnauthorizedError("Platform account is deactivated")

    g.platform_user = platform_user
    return platform_user


def platform_required(f):
    """Authenticate a platform route.

    The platform counterpart of `requires_module`: there is one platform role, so
    there is nothing finer to require. Marked so a coverage audit can recognise
    it the way it recognises `requires_module` and `jwt_required`.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticate_platform()
        return f(*args, **kwargs)

    decorated.__platform_only__ = True
    return decorated
