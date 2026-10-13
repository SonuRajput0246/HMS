import jwt
from functools import wraps
from sqlalchemy import select
from flask import request, current_app, g
from src.api.models.common.user_model import User
from src.api.models.common.token_model import Token
from src.database.session import db_session
from src.api.utils.errors import UnauthorizedError


def authenticate():
    """Validate the bearer token and return the caller.

    Split out of jwt_required so that jwt_required and
    authorization.requires_module share exactly one authentication path. Two
    copies of this is how the revocation check came to exist in one of them and
    not the other.

    Raises UnauthorizedError (401) for anything that makes the token unusable.
    """
    ## 1. Extract Token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Authorization token missing")

    token = auth_header.split(" ", 1)[1]

    try:
        ## 2. Decode Token
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )

        user_id = payload.get("user_id")
        if not user_id:
            raise UnauthorizedError("Invalid token payload")

        ## 3 Fetch User (SQLAlchemy 2.0 Syntax)
        stmt = select(User).filter_by(is_deleted=False, id=user_id)
        user = db_session.execute(stmt).scalar_one_or_none()
        if not user:
            raise UnauthorizedError("User not found or account deleted")

        if not user.is_active:
            raise UnauthorizedError("User account is deactivated")

        ## 3b. Enforce revocation.
        ##
        ## A decoded JWT used to be enough to get in, so
        ## AuthService.logout -- which sets Token.is_revoked on the user's
        ## live tokens -- had no effect: the same bearer token kept working
        ## until it expired by itself. Deactivating or deleting an account
        ## likewise left its issued tokens valid for the rest of their
        ## fifteen-minute life. The Token table and its ix_active_token
        ## (user_id, is_revoked) index existed for exactly this check, and
        ## nothing read them.
        ##
        ## Skipped for scoped tokens. The mfa_pending temp token minted at
        ## login is deliberately never persisted to `tokens`; the service
        ## checks it against /login/verify-totp, which is not authenticated
        ## here. Demanding a row for it would break MFA for no gain.
        if not payload.get("scope"):
            live = db_session.execute(
                select(Token.id).filter(
                    Token.user_id == user_id,
                    Token.access_token == token,
                    Token.is_revoked == False,
                ).limit(1)
            ).first()
            if live is None:
                raise UnauthorizedError("Token has been revoked")

        ## 4. Store in Global context
        g.current_user = user
        return user

    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")
    except UnauthorizedError:
        ## Re-raised unchanged. The blanket `except Exception` below would
        ## otherwise rewrite each of these into "Authorization failed", losing
        ## the reason a call was turned away.
        raise
    except Exception as e:
        raise UnauthorizedError(f"Authorization failed: {str(e)}")


def jwt_required(f):
    """Authenticate only.

    Prefer authorization.requires_module. The routes that legitimately need no
    module constraint are the self-service ones -- your own profile, your own
    password, MFA enrolment -- and those should say so explicitly with
    requires_module(SELF_SERVICE), which is what the route-coverage check in
    src/api/middlewares/authorization.py enforces.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticate()
        return f(*args, **kwargs)

    ## Marks a route as authenticated-but-undeclared. The audit reports every
    ## one as a coverage failure: the route gets past the token check with no
    ## module requirement, which is exactly the hole Phase 10 measured. Public
    ## routes carry neither marker.
    decorated.__auth_only__ = True
    return decorated