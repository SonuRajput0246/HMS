"""Dynamic auth test: can a token minted for hotel A be used at hotel B?

Phase 3 proved the *data* is isolated -- a query in one tenant cannot see
another's rows. This proves the *credentials* are, which is a different door:
a bearer token presented on the wrong host, and a refresh cookie that a browser
sends to whichever host it is talking to.

    python -m src.database.scripts.tenant_auth_test
    python -m src.database.scripts.tenant_auth_test --keep   # leave the db

It builds a throwaway database (`hms_authtest`) with `Base.metadata.create_all`,
seeds the platform rows, provisions `acme` and `globex`, then drives the real
HTTP surface with Flask's test client and asserts:

  1. LOGIN. Credentials for acme work at acme, and the minted access token
     carries `tenant_id == acme`.
  2. BINDING. The acme token is accepted at acme and refused at globex;
     a token with no claim, or with globex's claim, is refused at acme too.
  3. REFRESH. The acme refresh cookie is accepted at acme and refused at globex
     (the shared-localhost case the claim exists to cover).
  4. NO TENANT. A request that names no hotel is refused rather than served
     unscoped -- which is what stops a login from matching any hotel's user.
  5. CROSS CREDENTIALS. acme credentials are refused at globex, because the
     `users` lookup is scoped to the request's tenant.
  6. MFA. A `mfa_pending` temp token is bound the same way.

Exit code is 0 when every check passes and 1 otherwise.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import scoped_session, sessionmaker

from src.config import get_config

SCRATCH_DB = "hms_authtest"

_failures = []
_passes = 0


def check(label, ok, detail=""):
    global _passes
    if ok:
        _passes += 1
        print(f"  PASS  {label}")
    else:
        _failures.append(label)
        print(f"  FAIL  {label}")
        if detail:
            for line in str(detail).splitlines():
                print(f"          {line}")


## --------------------------------------------------------------------------
## setup / teardown
## --------------------------------------------------------------------------

def build_scratch_database():
    """Create an empty scratch schema and return (scratch_engine, admin_engine)."""
    url = make_url(get_config().DATABASE_URL)
    admin = create_engine(url.set(database="mysql"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
        conn.execute(text(
            f"CREATE DATABASE `{SCRATCH_DB}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))

    ## Rebinding the module-level session must happen BEFORE anything imports
    ## `db_session` by name -- the seeders, the routes, the app. They capture the
    ## object that exists at import time, so a later rebind would leave them
    ## pointed at the dev database.
    import src.database.session as session_module
    session_module.engine.dispose()
    scratch = create_engine(url.set(database=SCRATCH_DB), pool_pre_ping=True)
    session_module.engine = scratch
    session_module.session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=scratch
    )
    session_module.db_session = scoped_session(session_module.session_factory)

    import src.api.models  # noqa: F401  (populate the registry)
    import src.api.events.user_events  # noqa: F401
    import src.api.events.email_otp_events  # noqa: F401
    import src.api.events.role_events  # noqa: F401
    import src.api.events.inventory_events  # noqa: F401
    import src.api.events.room_events  # noqa: F401
    import src.api.events.reservation_events  # noqa: F401
    import src.api.events.guest_events  # noqa: F401
    import src.api.events.payment_events  # noqa: F401
    import src.api.events.tenant_events  # noqa: F401
    import src.api.events.platform_user_events  # noqa: F401

    from src.database.base import Base
    Base.metadata.create_all(scratch)

    return scratch, admin


def provision_two_hotels():
    """Seed the platform, then two hotels. Returns (acme_id, globex_id)."""
    from src.database.seeders.run_base_seeders import seed_platform_data
    from src.database.seeders.provision_tenant import provision_tenant

    seed_platform_data()
    acme = provision_tenant("acme", "Acme Hotel", "admin@acme.test", "pw-acme-123")
    globex = provision_tenant("globex", "Globex Hotel", "admin@globex.test", "pw-globex-123")
    return acme.id, globex.id


def drop_scratch_database(scratch, admin):
    from src.database.session import db_session
    db_session.remove()
    scratch.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
    admin.dispose()


## --------------------------------------------------------------------------
## checks
## --------------------------------------------------------------------------

def decode(token, application):
    return jwt.decode(
        token,
        application.config["JWT_SECRET_KEY"],
        algorithms=[application.config["JWT_ALGORITHM"]],
    )


def forge(application, claims):
    now = datetime.now(timezone.utc)
    body = {"iat": now, "exp": now + timedelta(minutes=15), **claims}
    return jwt.encode(
        body,
        application.config["JWT_SECRET_KEY"],
        algorithm=application.config["JWT_ALGORITHM"],
    )


def protected(client, token, tenant):
    return client.post(
        "/api/v1/common/get-all-currencies",
        json={},
        headers={"X-Tenant": tenant, "Authorization": f"Bearer {token}"},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true",
                        help="leave the scratch database in place")
    args = parser.parse_args()

    scratch = admin = None
    try:
        scratch, admin = build_scratch_database()

        ## A real app context, and importing `app` only now -- after the session
        ## was rebound -- so the routes and services it imports capture the
        ## scratch session rather than the dev one.
        import app as flask_app
        application = flask_app.create_app()
        application.config["TESTING"] = True

        with application.app_context():
            acme_id, globex_id = provision_two_hotels()
        print(f"\nprovisioned acme (id={acme_id}) and globex (id={globex_id})")

        from src.database.session import db_session as db
        from src.api.models import User
        from src.database.tenant_context import tenant_context
        with tenant_context(acme_id):
            acme_admin_id = db.execute(
                select(User.id).where(User.email == "admin@acme.test")
            ).scalar_one()

        client = application.test_client()

        print("\n[1] login mints a tenant-bound token")
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@acme.test", "password": "pw-acme-123"},
            headers={"X-Tenant": "acme"},
        )
        check("login on acme returns 200", response.status_code == 200,
              response.get_data(as_text=True)[:400])
        body = response.get_json(silent=True) or {}
        data = body.get("data") or {}
        token = data.get("access_token")
        check("the login response carries an access token", bool(token))
        check("the login response sets the refresh cookie",
              client.get_cookie("hms_refreshToken") is not None)
        if token:
            check("the access token carries tenant_id == acme",
                  decode(token, application).get("tenant_id") == acme_id,
                  decode(token, application))

        print("\n[2] the token is accepted only at its own hotel")
        check("the acme token is accepted at acme",
              protected(client, token, "acme").status_code == 200)
        check("the acme token is refused at globex",
              protected(client, token, "globex").status_code == 401,
              protected(client, token, "globex").get_data(as_text=True)[:200])
        check("a token with no tenant claim is refused",
              protected(client, forge(application, {"user_id": acme_admin_id}),
                        "acme").status_code == 401)
        check("a token carrying globex's claim is refused at acme",
              protected(client, forge(application, {"user_id": acme_admin_id,
                                                    "tenant_id": globex_id}),
                        "acme").status_code == 401)

        print("\n[3] the refresh cookie is bound too")
        refresh_cookie = client.get_cookie("hms_refreshToken")
        crossed = client.post(
            "/api/v1/auth/get-fresh-token",
            json={},
            headers={"X-Tenant": "globex",
                     "Cookie": f"hms_refreshToken={refresh_cookie.value}"},
        )
        check("the acme refresh cookie is refused at globex",
              crossed.status_code == 401,
              crossed.get_data(as_text=True)[:200])
        accepted = client.post(
            "/api/v1/auth/get-fresh-token",
            json={},
            headers={"X-Tenant": "acme",
                     "Cookie": f"hms_refreshToken={refresh_cookie.value}"},
        )
        check("the acme refresh cookie is accepted at acme",
              accepted.status_code == 200,
              accepted.get_data(as_text=True)[:200])

        print("\n[4] a request that names no hotel is refused")
        unnamed = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@acme.test", "password": "pw-acme-123"},
        )
        check("login with no tenant returns 404", unnamed.status_code == 404,
              unnamed.get_data(as_text=True)[:200])

        print("\n[5] another hotel's credentials do not work")
        wrong_hotel = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@acme.test", "password": "pw-acme-123"},
            headers={"X-Tenant": "globex"},
        )
        check("acme credentials are refused at globex",
              wrong_hotel.status_code == 401,
              wrong_hotel.get_data(as_text=True)[:200])

        print("\n[6] the mfa_pending temp token is bound too")
        temp = forge(application, {"user_id": acme_admin_id, "tenant_id": acme_id,
                                   "scope": "mfa_pending"})
        mfa_crossed = client.post(
            "/api/v1/auth/login/verify-totp",
            json={"temp_token": temp, "totp": "000000"},
            headers={"X-Tenant": "globex"},
        )
        check("the acme mfa temp token is refused at globex",
              mfa_crossed.status_code == 401,
              mfa_crossed.get_data(as_text=True)[:200])

        print(f"\n  {_passes} passed, {len(_failures)} failed")
        if not args.keep:
            drop_scratch_database(scratch, admin)
        return 1 if _failures else 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
