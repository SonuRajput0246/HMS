"""Server-side authorization.

Until now the only thing standing between a logged-in account and the sales
report was the Angular AuthGuard, which runs in the browser. Phase 10 measured
it: a user whose role was granted *nothing* got 200 from 19 of 19 probed
endpoints -- every report, the customer list, the user list, the role list. The
`menu_access` payload is computed correctly and travels correctly; nothing on
the server ever read it.

This module makes it the server's decision.

Design notes worth keeping:

* **Modules are named, not numbered.** Module ids are an artefact of the seeder
  and carry no meaning. Keying enforcement on the name, resolved against the
  live module tree, means a re-seed that renumbers cannot silently change who
  can reach what.

* **There is no wildcard.** ROLE_PERMISSIONS gives SUPER_ADMIN a "*", but
  role_seeder expands it into concrete role_module_access rows at seed time. So
  a super admin is simply a role holding every module, and needs no special
  case here.

* **Deny by default.** Every authenticated route must say what it needs.
  requires_module("REPORTS") or requires_module(SELF_SERVICE). A route still
  wrapped in bare jwt_required is a coverage failure, which
  `python -m src.database.scripts.audit_authorization` reports.

* **Module-level only, deliberately.** role_module_access stores operations
  too (View/Create/Edit/Delete/Export/Payment/Void/Split) and they are carried
  in menu_access, but enforcing them means classifying every route against that
  taxonomy, and a misclassified route either blocks real work or quietly
  under-enforces. Module-level closes the hole that exists today; the
  operation-level pass is a separate decision.
"""
import logging
from functools import wraps

from flask import g
from sqlalchemy import select

from src.api.middlewares.auth_middleware import authenticate
from src.api.models.module_model import Module
from src.api.models.role_module_access_model import RoleModuleAccess
from src.database.session import db_session
from src.api.utils.errors import APIError


## Marker for routes that need a valid session but no module of their own:
## your own profile, your own password, MFA enrolment, logout. Written out
## rather than defaulted, so "needs no module" is always a decision someone
## made and can be grepped for.
SELF_SERVICE = "__self_service__"

## Operations that mean "can see this module at all". A role row for a module
## always carries at least one, but a module granted only via an operation
## this list does not contain would otherwise be invisible here.
_ANY_OPERATION = None


class ForbiddenError(APIError):
    def __init__(self, message="You do not have access to this resource",
                 payload=None):
        super().__init__(message, status_code=403, payload=payload)


def granted_module_names(role_id):
    """Module names the given role can reach.

    Deliberately mirrors the filters in AuthService._build_menu_access -- active
    access rows, joined to active modules -- so the server's decision and the
    menu the frontend renders cannot drift apart. If that method's filters
    change, this must change with it.

    There is no wildcard branch because there is no runtime wildcard; see the
    module docstring.
    """
    names = {
        row.module_name
        for row in db_session.execute(
            select(Module.module_name)
            .join(RoleModuleAccess, RoleModuleAccess.module_id == Module.id)
            .filter(
                RoleModuleAccess.role_id == role_id,
                RoleModuleAccess.is_active == True,
                RoleModuleAccess.is_deleted == False,
                Module.is_active == True,
                Module.is_deleted == False,
            )
        ).all()
    }
    return names


def granted_modules_for_request():
    """The caller's granted module names, resolved once per request.

    Cached on flask.g, which is per-request, so a request that hits several
    decorators -- nested blueprints -- pays for one lookup rather than several.
    """
    cached = getattr(g, "_granted_modules", None)
    if cached is not None:
        return cached
    user = getattr(g, "current_user", None)
    names = granted_module_names(user.role_id) if user and user.role_id else set()
    g._granted_modules = names
    return names


def can_access(module_name):
    if module_name == SELF_SERVICE:
        return True
    return module_name in granted_modules_for_request()


def requires_module(module_name):
    """Authenticate, then require `module_name`.

    Wraps authentication itself so a route cannot end up protected by one and
    not the other: there is exactly one decorator in front of every
    authenticated view, and it does both jobs.

    module_name is a module name as it appears in the module seeder
    (REPORTS, TABLE, RESERVATIONS, ...), or SELF_SERVICE for routes that only
    need a valid session.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = authenticate()
            g.required_module = module_name

            if module_name != SELF_SERVICE:
                granted = granted_modules_for_request()
                if module_name not in granted:
                    ## Logged at warning, not error: a 403 on a legitimate
                    ## request is the system working, not a fault. A module
                    ## absent from the tree entirely is a different problem --
                    ## the module tree has not been seeded -- so that one is
                    ## worth an error.
                    if not _module_exists(module_name):
                        logging.error(
                            "Authorization refused: module %r is not in the "
                            "module tree. Run the seeders so the tree exists. "
                            "user_id=%s",
                            module_name, getattr(user, "id", None),
                        )
                    else:
                        logging.warning(
                            "Authorization refused: user_id=%s role_id=%s "
                            "lacks module %r",
                            getattr(user, "id", None),
                            getattr(user, "role_id", None),
                            module_name,
                        )
                    raise ForbiddenError(
                        "You do not have access to this resource",
                        payload={
                            "required_module": module_name,
                            "granted_modules": sorted(granted),
                        },
                    )

            return f(*args, **kwargs)

        ## Read by the route-coverage audit. Set here rather than inferred from
        ## the function name, so a route can be recognised regardless of how
        ## it was wrapped.
        decorated.__required_module__ = module_name
        return decorated

    return decorator


def _module_exists(module_name):
    """Is this module present in the running instance's tree?

    Lets the refusal above distinguish "this user lacks it" from "the tree is
    wrong", which is the failure mode Phase 8 described and which used to be
    completely silent.
    """
    cached = getattr(g, "_module_tree", None)
    if cached is None:
        cached = {
            row.module_name
            for row in db_session.execute(
                select(Module.module_name).filter(
                    Module.is_active == True, Module.is_deleted == False
                )
            ).all()
        }
        g._module_tree = cached
    return module_name in cached