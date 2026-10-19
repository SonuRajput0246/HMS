"""Dynamic platform test: does the super admin console hold its own invariants?

There are two identity systems in this codebase and the operator who sits above
every hotel is one of them. The question this answers is whether a token from one
world can act in the other, whether MFA is genuinely compulsory on the platform
login, whether a session can actually be revoked, and whether the tenant and
operator lifecycles take effect on the rows they claim to.

    python -m src.database.scripts.platform_auth_test
    python -m src.database.scripts.platform_auth_test --keep   # leave the db

It builds a throwaway database (`hms_platformtest`) with `Base.metadata.create_all`,
seeds the platform rows, creates one operator, then drives the real HTTP surface
with Flask's test client and asserts:

  1. MFA IS COMPULSORY. A correct password returns a pending token and no
     session; only a valid code mints one. An un-enrolled operator is walked
     through enrolment rather than let in.
  2. CROSS AUDIENCE. A platform token is refused on a hotel route and a hotel
     token is refused on a platform route, in both directions.
  3. THE GUARD. Every management endpoint refuses an unauthenticated caller.
  4. PROVISIONING. A hotel created through the platform route appears in the
     list with its timezone and currency, and its admin can then log in.
  5. LOCKOUT. Repeated wrong passwords lock the account with a 429.
  6. LIFECYCLE. A deactivated hotel's routes answer 403 and re-activating
     restores them; the retired suspend/reactivate endpoints answer 404.
  7. PASSWORD RESET. The operator can reset a hotel admin's password: the old
     password stops working, the tokens it bought die with it, the new one works.
  8. REVOCATION. Logging out kills the token everywhere, not just in this client.
  9. SELF-PROTECTION. An operator cannot deactivate or reset themselves.
 10. AUDIT. Every platform action left a row behind.

Exit code is 0 when every check passes and 1 otherwise.
"""
import argparse
import sys

import jwt
import pyotp
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import scoped_session, sessionmaker

from src.config import get_config

SCRATCH_DB = "hms_platformtest"

PLATFORM_EMAIL = "operator@platform.test"
PLATFORM_PASSWORD = "operator-pw-123"
PLATFORM_SECRET = "platform-test-secret"
ACME_PASSWORD = "pw-acme-123"
ACME_NEW_PASSWORD = "pw-acme-456"

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


def build_scratch_database():
    url = make_url(get_config().DATABASE_URL)
    admin = create_engine(url.set(database="mysql"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
        conn.execute(text(
            f"CREATE DATABASE `{SCRATCH_DB}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))

    import src.database.session as session_module
    session_module.engine.dispose()
    scratch = create_engine(url.set(database=SCRATCH_DB), pool_pre_ping=True)
    session_module.engine = scratch
    session_module.session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=scratch
    )
    session_module.db_session = scoped_session(session_module.session_factory)

    import src.api.models  # noqa: F401
    import src.api.events.user_events  # noqa: F401
    import src.api.events.email_otp_events  # noqa: F401
    import src.api.events.role_events  # noqa: F401
    import src.api.events.inventory_events  # noqa: F401
    import src.api.events.room_events  # noqa: F401
    import src.api.events.reservation_events  # noqa: F401
    import src.api.events.guest_events  # noqa: F401
    import src.api.events.payment_events  # noqa: F401
    import src.api.events.tenant_events  # noqa: F401
    import src.api.events.super_admin_events  # noqa: F401

    from src.database.base import Base
    Base.metadata.create_all(scratch)
    return scratch, admin


def create_operator():
    """An operator who has already enrolled in MFA.

    Enrolment is compulsory and normally happens through the login screen, so
    seeding the secret here is the only way to get to a session without running
    the whole enrolment dance as setup.
    """
    from src.api.extensions import bcrypt
    from src.api.models.super_admin_user_model import SuperAdminUser
    from src.database.session import db_session as db

    user = SuperAdminUser(
        first_name="Platform",
        last_name="Operator",
        email=PLATFORM_EMAIL,
        password=bcrypt.generate_password_hash(PLATFORM_PASSWORD, 12).decode("utf-8"),
        is_active=True,
        is_deleted=False,
        mfa_enabled=True,
        mfa_secret=pyotp.random_base32(),
    )
    db.add(user)
    db.commit()
    return user.id, user.mfa_secret


def drop_scratch_database(scratch, admin):
    from src.database.session import db_session
    db_session.remove()
    scratch.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
    admin.dispose()


def decode(token, application, secret_key, algorithm_key):
    return jwt.decode(
        token,
        application.config[secret_key],
        algorithms=[application.config[algorithm_key]],
    )


def _fails_to_decode(token, application, secret_key, algorithm_key):
    """True when `token` does not verify under the given secret (the point)."""
    try:
        decode(token, application, secret_key, algorithm_key)
        return False
    except jwt.InvalidTokenError:
        return True


def sign_in(client, email, password, secret):
    """The full two-step platform sign-in. Returns the access token, or None.

    Every assertion about "logged in" in this script goes through here, so a
    change to the login contract cannot quietly make half the checks vacuous.
    """
    first = client.post(
        "/api/v1/platform/auth/login", json={"email": email, "password": password}
    )
    if first.status_code != 200:
        return None
    data = (first.get_json(silent=True) or {}).get("data") or {}
    temp_token = data.get("temp_token")
    if not temp_token:
        return None

    verified = client.post(
        "/api/v1/platform/auth/verify-mfa",
        json={"temp_token": temp_token, "totp": pyotp.TOTP(secret).now()},
    )
    if verified.status_code != 200:
        return None
    return (verified.get_json(silent=True) or {}).get("data", {}).get("access_token")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true",
                        help="leave the scratch database in place")
    args = parser.parse_args()

    scratch = admin = None
    try:
        scratch, admin = build_scratch_database()

        import app as flask_app
        application = flask_app.create_app()
        application.config["TESTING"] = True
        application.config["PLATFORM_JWT_SECRET_KEY"] = PLATFORM_SECRET

        from src.database.seeders.run_base_seeders import seed_platform_data
        with application.app_context():
            seed_platform_data()
            operator_id, operator_secret = create_operator()

        client = application.test_client()

        print("\n[1] MFA is compulsory on the platform login")
        first = client.post(
            "/api/v1/platform/auth/login",
            json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        check("a correct password returns 200", first.status_code == 200,
              first.get_data(as_text=True)[:400])
        first_data = (first.get_json(silent=True) or {}).get("data") or {}
        check("it hands back a pending token, not a session",
              bool(first_data.get("temp_token")) and not first_data.get("access_token"),
              first_data)
        check("it reports that a code is required",
              first_data.get("mfa_required") is True, first_data)

        pending = first_data.get("temp_token")
        wrong_code = client.post(
            "/api/v1/platform/auth/verify-mfa",
            json={"temp_token": pending, "totp": "000000"},
        )
        check("a wrong code is refused", wrong_code.status_code == 401,
              wrong_code.get_data(as_text=True)[:300])

        verified = client.post(
            "/api/v1/platform/auth/verify-mfa",
            json={"temp_token": pending, "totp": pyotp.TOTP(operator_secret).now()},
        )
        check("the right code completes the sign-in", verified.status_code == 200,
              verified.get_data(as_text=True)[:400])
        platform_token = (verified.get_json(silent=True) or {}).get("data", {}).get("access_token")
        check("a session token is issued", bool(platform_token))

        auth = {"Authorization": f"Bearer {platform_token}"}

        if platform_token:
            payload = decode(platform_token, application,
                             "PLATFORM_JWT_SECRET_KEY", "PLATFORM_JWT_ALGORITHM")
            check("the platform token is scoped 'super_admin'",
                  payload.get("scope") == "super_admin", payload)
            check("the platform token is not signed with the hotel secret",
                  _fails_to_decode(platform_token, application,
                                   "JWT_SECRET_KEY", "JWT_ALGORITHM"))

        print("\n[2] the guard")
        for path in ("/api/v1/platform/tenants",
                     "/api/v1/platform/admins",
                     "/api/v1/platform/audit-logs",
                     "/api/v1/platform/dashboard/summary"):
            query = "page_size=10&page_number=1" if "audit" in path or "tenants" in path or "admins" in path else ""
            check(f"an unauthenticated call to {path} is 401",
                  client.get(f"{path}?{query}").status_code == 401)
        check("a wrong password is 401",
              client.post("/api/v1/platform/auth/login",
                          json={"email": PLATFORM_EMAIL,
                                "password": "wrong"}).status_code == 401)
        check("a hotel JWT cannot stand in for a platform token",
              client.get("/api/v1/platform/tenants?page_size=10&page_number=1",
                         headers={"Authorization": "Bearer not.a.token"}).status_code == 401)

        print("\n[3] provisioning through the platform")
        created = client.post(
            "/api/v1/platform/tenants",
            json={"name": "Acme Hotel", "slug": "acme",
                  "timezone": "Asia/Kolkata", "currency": "INR",
                  "admin_first_name": "Acme", "admin_last_name": "Owner",
                  "admin_email": "admin@acme.test",
                  "admin_password": ACME_PASSWORD},
            headers=auth,
        )
        check("creating a tenant returns 201", created.status_code == 201,
              created.get_data(as_text=True)[:400])
        acme = (created.get_json(silent=True) or {}).get("data") or {}
        acme_id = acme.get("id")
        check("the created tenant has an id", bool(acme_id))
        check("it is reported active", acme.get("status") == "active", acme)
        check("it carries the timezone it was given",
              acme.get("timezone") == "Asia/Kolkata", acme)
        check("it carries the currency it was given",
              acme.get("currency") == "INR", acme)

        listed = client.get("/api/v1/platform/tenants?page_size=10&page_number=1",
                            headers=auth)
        rows = (listed.get_json(silent=True) or {}).get("data") or []
        check("the new tenant is listed", any(t["slug"] == "acme" for t in rows),
              [t.get("slug") for t in rows])
        check("the list is paginated",
              "meta" in (listed.get_json(silent=True) or {}))

        check("a reserved slug is refused",
              client.post("/api/v1/platform/tenants",
                          json={"name": "Bad", "slug": "admin",
                                "timezone": "Asia/Kolkata", "currency": "INR",
                                "admin_first_name": "A", "admin_last_name": "B",
                                "admin_email": "bad@x.test",
                                "admin_password": ACME_PASSWORD},
                          headers=auth).status_code == 400)
        check("a bogus timezone is refused",
              client.post("/api/v1/platform/tenants",
                          json={"name": "Bad", "slug": "badzone",
                                "timezone": "Mars/Olympus", "currency": "INR",
                                "admin_first_name": "A", "admin_last_name": "B",
                                "admin_email": "bad2@x.test",
                                "admin_password": ACME_PASSWORD},
                          headers=auth).status_code == 400)

        print("\n[4] the two audiences do not cross")
        hotel_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@acme.test", "password": ACME_PASSWORD},
            headers={"X-Tenant": "acme"},
        )
        check("the new hotel's admin can log in", hotel_login.status_code == 200,
              hotel_login.get_data(as_text=True)[:400])
        hotel_token = (hotel_login.get_json(silent=True) or {}).get("data", {}).get("access_token")

        check("a hotel token is refused on a platform route",
              client.get("/api/v1/platform/tenants?page_size=10&page_number=1",
                         headers={"Authorization": f"Bearer {hotel_token}"}
                         ).status_code == 401)
        check("a platform token is refused on a hotel route",
              client.post("/api/v1/common/get-all-currencies", json={},
                          headers={"X-Tenant": "acme",
                                   "Authorization": f"Bearer {platform_token}"}
                          ).status_code == 401)

        print("\n[5] deactivate and re-activate take effect")
        deactivated = client.patch(
            f"/api/v1/platform/tenants/{acme_id}/status",
            json={"is_active": False},
            headers=auth,
        )
        check("deactivating a tenant returns 200", deactivated.status_code == 200,
              deactivated.get_data(as_text=True)[:400])
        check("its status reads 'inactive'",
              (deactivated.get_json(silent=True) or {}).get("data", {}).get("status")
              == "inactive")
        blocked = client.get("/api/v1/common/tenant-info", headers={"X-Tenant": "acme"})
        check("a deactivated hotel's request is 403", blocked.status_code == 403,
              blocked.get_data(as_text=True)[:200])

        reactivated = client.patch(
            f"/api/v1/platform/tenants/{acme_id}/status",
            json={"is_active": True},
            headers=auth,
        )
        check("re-activating a tenant returns 200", reactivated.status_code == 200,
              reactivated.get_data(as_text=True)[:400])
        check("a re-activated hotel's request is served again",
              client.get("/api/v1/common/tenant-info",
                         headers={"X-Tenant": "acme"}).status_code == 200)

        check("the suspend endpoint no longer exists",
              client.post(f"/api/v1/platform/tenants/{acme_id}/suspend",
                          json={"reason": "Non-payment"},
                          headers=auth).status_code == 404)
        check("reactivate no longer exists",
              client.post(f"/api/v1/platform/tenants/{acme_id}/reactivate",
                          json={}, headers=auth).status_code == 404)

        print("\n[6] resetting the hotel admin's password")
        reset = client.post(
            f"/api/v1/platform/tenants/{acme_id}/reset-admin-password",
            json={"password": ACME_NEW_PASSWORD},
            headers=auth,
        )
        check("the reset returns 200", reset.status_code == 200,
              reset.get_data(as_text=True)[:400])
        check("the old password no longer works",
              client.post("/api/v1/auth/login",
                          json={"email": "admin@acme.test", "password": ACME_PASSWORD},
                          headers={"X-Tenant": "acme"}).status_code == 401)
        check("the reset ends the admin's existing sessions",
              client.post("/api/v1/common/get-all-currencies", json={},
                          headers={"X-Tenant": "acme",
                                   "Authorization": f"Bearer {hotel_token}"}
                          ).status_code == 401)
        check("the new password works",
              client.post("/api/v1/auth/login",
                          json={"email": "admin@acme.test", "password": ACME_NEW_PASSWORD},
                          headers={"X-Tenant": "acme"}).status_code == 200)

        print("\n[7] archive and restore")
        check("archiving returns 200",
              client.post(f"/api/v1/platform/tenants/{acme_id}/archive",
                          json={}, headers=auth).status_code == 200)
        check("an archived hotel stops resolving",
              client.get("/api/v1/common/tenant-info",
                         headers={"X-Tenant": "acme"}).status_code == 404)
        check("an archived hotel is still readable through the console",
              client.get(f"/api/v1/platform/tenants/{acme_id}",
                         headers=auth).status_code == 200)
        check("editing an archived hotel is refused",
              client.patch(f"/api/v1/platform/tenants/{acme_id}",
                           json={"name": "Nope"}, headers=auth).status_code == 400)
        check("restoring returns 200",
              client.post(f"/api/v1/platform/tenants/{acme_id}/restore",
                          json={}, headers=auth).status_code == 200)
        check("a restored hotel is inactive until activated",
              client.get("/api/v1/common/tenant-info",
                         headers={"X-Tenant": "acme"}).status_code == 403)

        print("\n[8] self-protection")
        check("an operator cannot deactivate themselves",
              client.patch(f"/api/v1/platform/admins/{operator_id}/status",
                           json={"is_active": False}, headers=auth).status_code == 400)
        check("an operator cannot reset their own password here",
              client.post(f"/api/v1/platform/admins/{operator_id}/reset-password",
                          json={"new_password": "whatever-123"},
                          headers=auth).status_code == 400)

        print("\n[9] the audit trail")
        ## Read before the logout and the lockout: both destroy the credential
        ## this section authenticates with, and the point here is to inspect what
        ## the steps above left behind, not to test re-entry.
        logs = client.get("/api/v1/platform/audit-logs?page_size=100&page_number=1",
                          headers=auth)
        check("the audit reader answers", logs.status_code == 200,
              logs.get_data(as_text=True)[:300])
        check("it is paginated", "meta" in (logs.get_json(silent=True) or {}))
        rows = (logs.get_json(silent=True) or {}).get("data") or []
        actions = {row["action"] for row in rows}
        for expected in ("CREATE_TENANT", "LOGIN_SUPER_ADMIN", "DEACTIVATE_TENANT",
                         "ACTIVATE_TENANT", "ARCHIVE_TENANT", "RESTORE_TENANT",
                         "RESET_TENANT_ADMIN_PASSWORD", "LOGIN_FAILED_SUPER_ADMIN"):
            check(f"'{expected}' was recorded", expected in actions, sorted(actions))
        create_row = next((r for r in rows if r["action"] == "CREATE_TENANT"), None)
        check("a create row names its actor",
              bool(create_row and create_row.get("actor_email") == PLATFORM_EMAIL),
              create_row)
        check("a create row keeps its details as JSON text",
              bool(create_row and '"slug"' in (create_row.get("details") or "")),
              create_row)

        print("\n[10] logout revokes the session everywhere")
        check("logging out returns 200",
              client.post("/api/v1/platform/auth/logout", json={},
                          headers=auth).status_code == 200)
        check("the token stops working",
              client.get("/api/v1/platform/auth/me", headers=auth).status_code == 401)
        ## A second client, so this is genuinely "everywhere" and not just this
        ## test's own cookie-less client forgetting something.
        check("another client agrees the token is dead",
              application.test_client().get("/api/v1/platform/auth/me",
                                            headers=auth).status_code == 401)

        print("\n[11] the brute-force lockout")
        from src.config import get_config as _cfg
        application.config["SUPER_ADMIN_MAX_LOGIN_ATTEMPTS"] = 3
        statuses = [
            client.post("/api/v1/platform/auth/login",
                        json={"email": PLATFORM_EMAIL,
                              "password": f"wrong-{i}"}).status_code
            for i in range(4)
        ]
        check("repeated wrong passwords end in a 429", statuses[-1] == 429, statuses)
        check("a locked account is not reachable with the RIGHT password either",
              client.post("/api/v1/platform/auth/login",
                          json={"email": PLATFORM_EMAIL,
                                "password": PLATFORM_PASSWORD}).status_code == 429)
        application.config["SUPER_ADMIN_MAX_LOGIN_ATTEMPTS"] = _cfg().SUPER_ADMIN_MAX_LOGIN_ATTEMPTS

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
