"""Dynamic platform test: do the two identity systems stay apart?

Phase 4a-4d bound hotel tokens to a hotel. This covers the other identity in the
system: the platform operator, who belongs to no hotel and administers all of
them. The question is whether a token from one world can act in the other, and
whether the platform's two powers this phase adds -- suspending a hotel and
resetting its admin's password -- actually take effect.

    python -m src.database.scripts.platform_auth_test
    python -m src.database.scripts.platform_auth_test --keep   # leave the db

It builds a throwaway database (`hms_platformtest`) with `Base.metadata.create_all`,
seeds the platform rows, creates one platform user, then drives the real HTTP
surface with Flask's test client and asserts:

  1. LOGIN. The platform user gets a token whose scope is `platform`.
  2. CROSS AUDIENCE. A platform token is refused on a hotel route and a hotel
     token is refused on a platform route, in both directions.
  3. PROVISIONING. A hotel created through the platform route appears in the
     list, and its admin can then log in.
  4. SUSPEND / REACTIVATE. A suspended hotel's routes answer 403; reactivating
     restores them.
  5. PASSWORD RESET. The platform can reset a hotel admin's password: the old
     password stops working and the new one works.
  6. GUARD. An unauthenticated platform call is 401.

Exit code is 0 when every check passes and 1 otherwise.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

import jwt
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
    import src.api.events.platform_user_events  # noqa: F401

    from src.database.base import Base
    Base.metadata.create_all(scratch)
    return scratch, admin


def create_platform_user():
    from src.api.extensions import bcrypt
    from src.api.models.platform_user_model import PlatformUser
    from src.database.session import db_session as db

    user = PlatformUser(
        email=PLATFORM_EMAIL,
        password=bcrypt.generate_password_hash(PLATFORM_PASSWORD, 12).decode("utf-8"),
        first_name="Platform",
        last_name="Operator",
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    db.commit()
    return user.id


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
            create_platform_user()

        client = application.test_client()

        print("\n[1] the platform user logs in")
        response = client.post(
            "/api/v1/platform/login",
            json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        check("platform login returns 200", response.status_code == 200,
              response.get_data(as_text=True)[:400])
        body = response.get_json(silent=True) or {}
        platform_token = (body.get("data") or {}).get("access_token")
        check("platform login carries an access token", bool(platform_token))
        if platform_token:
            payload = decode(platform_token, application,
                             "PLATFORM_JWT_SECRET_KEY", "PLATFORM_JWT_ALGORITHM")
            check("the platform token is scoped 'platform'",
                  payload.get("scope") == "platform", payload)
            check("the platform token is not signed with the hotel secret",
                  _fails_to_decode(platform_token, application,
                                   "JWT_SECRET_KEY", "JWT_ALGORITHM"))

        print("\n[2] the guard")
        check("an unauthenticated platform call is 401",
              client.get("/api/v1/platform/tenants").status_code == 401)
        check("a platform login with the wrong password is 401",
              client.post("/api/v1/platform/login",
                          json={"email": PLATFORM_EMAIL,
                                "password": "wrong"}).status_code == 401)

        print("\n[3] provisioning through the platform")
        created = client.post(
            "/api/v1/platform/tenants",
            json={"slug": "acme", "name": "Acme Hotel",
                  "admin_email": "admin@acme.test",
                  "admin_password": ACME_PASSWORD},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        check("creating a tenant returns 201", created.status_code == 201,
              created.get_data(as_text=True)[:400])
        acme_id = (created.get_json(silent=True) or {}).get("data", {}).get("id")
        check("the created tenant has an id", bool(acme_id))

        listed = client.get(
            "/api/v1/platform/tenants",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        slugs = [t["slug"] for t in (listed.get_json(silent=True) or {}).get("data", [])]
        check("the new tenant is listed", "acme" in slugs, slugs)

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
              client.get("/api/v1/platform/tenants",
                         headers={"Authorization": f"Bearer {hotel_token}"}
                         ).status_code == 401)
        check("a platform token is refused on a hotel route",
              client.post("/api/v1/common/get-all-currencies", json={},
                          headers={"X-Tenant": "acme",
                                   "Authorization": f"Bearer {platform_token}"}
                          ).status_code == 401)

        print("\n[5] suspend and reactivate take effect")
        suspended = client.post(
            f"/api/v1/platform/tenants/{acme_id}/suspend",
            json={"reason": "Non-payment"},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        check("suspending a tenant returns 200", suspended.status_code == 200,
              suspended.get_data(as_text=True)[:400])
        blocked = client.get("/api/v1/common/tenant-info",
                             headers={"X-Tenant": "acme"})
        check("a suspended hotel's request is 403", blocked.status_code == 403,
              blocked.get_data(as_text=True)[:200])

        reactivated = client.post(
            f"/api/v1/platform/tenants/{acme_id}/reactivate",
            json={},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        check("reactivating a tenant returns 200", reactivated.status_code == 200,
              reactivated.get_data(as_text=True)[:400])
        check("a reactivated hotel's request is served again",
              client.get("/api/v1/common/tenant-info",
                         headers={"X-Tenant": "acme"}).status_code == 200)

        print("\n[6] resetting the hotel admin's password")
        reset = client.post(
            f"/api/v1/platform/tenants/{acme_id}/reset-admin-password",
            json={"password": ACME_NEW_PASSWORD},
            headers={"Authorization": f"Bearer {platform_token}"},
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

        print(f"\n  {_passes} passed, {len(_failures)} failed")
        if not args.keep:
            drop_scratch_database(scratch, admin)
        return 1 if _failures else 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


def _fails_to_decode(token, application, secret_key, algorithm_key):
    """True when `token` does not verify under the given secret (the point)."""
    try:
        decode(token, application, secret_key, algorithm_key)
        return False
    except jwt.InvalidTokenError:
        return True


if __name__ == "__main__":
    sys.exit(main())
