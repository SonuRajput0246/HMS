"""Dynamic branding test: do two hotels send differently-branded mail?

Phase 6 makes a hotel's brand a per-tenant value (`system_settings.company_name`)
rather than a global one. Before this phase the send path read
`current_app.config["COMPANY_NAME"]` -- a key that was never set anywhere -- so
every hotel on the install signed its mail "HMS", and the layout footer and the
seeded OTP body hardcoded the product name as well.

    python -m src.database.scripts.tenant_branding_test
    python -m src.database.scripts.tenant_branding_test --keep   # leave the db

It builds a throwaway database (`hms_brandingtest`), seeds the platform,
provisions `acme` and `globex`, then asserts:

  1. DEFAULT. Each hotel's `company_name` is seeded from its own display name.
  2. BRANDED MAIL. A mail sent for each hotel, captured at the SMTP boundary,
     carries that hotel's brand in the footer and sign-off -- and does not carry
     the other hotel's brand, nor the generic "HMS".
  3. SETTINGS, NOT THE REGISTRY. Changing the setting (not the tenant row)
     changes the mail.
  4. PUBLIC BRANDING. `GET /api/v1/common/tenant-info` reports each hotel's own
     branding, unscoped by any token.
  5. SEEDED CONTENT. The seeded login-slider welcome names the hotel, not the
     product.
  6. GUEST ROLE. Public self-registration grants the hotel's GUEST role, never
     the first-seeded SUPER_ADMIN it used to hardcode (`role_id=1`).

The SMTP call is stubbed; everything else is the real service path.

Exit code is 0 when every check passes and 1 otherwise.
"""
import argparse
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import scoped_session, sessionmaker

from src.config import get_config

SCRATCH_DB = "hms_brandingtest"

ACME_NAME = "Acme Hotel"
GLOBEX_NAME = "Globex Hotel"
ACME_BRAND = "Acme Grand"
GLOBEX_BRAND = "Globex Resorts"
PRODUCT_FALLBACK = "HMS"

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


def drop_scratch_database(scratch, admin):
    from src.database.session import db_session
    db_session.remove()
    scratch.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
    admin.dispose()


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

        ## Capture the mail at the SMTP boundary. `EmailService` calls the
        ## module-level `send_email`, so patching it here intercepts the real
        ## send path without a network.
        from src.api.services import email_service as email_service_module
        captured = []

        def capture(receiver_email, subject, html_body):
            captured.append({"to": receiver_email, "subject": subject, "html": html_body})
            return True

        email_service_module.send_email = capture

        from src.database.session import db_session as db
        from src.database.tenant_context import tenant_context
        from src.database.seeders.run_base_seeders import seed_platform_data
        from src.database.seeders.provision_tenant import provision_tenant
        from src.api.models import Role, SystemSetting, User
        from src.api.models.login_sliders_model import LoginSliders
        from src.api.services.email_service import EmailService
        from src.api.utils.tenant_settings import get_tenant_setting

        with application.app_context():
            seed_platform_data()
            acme = provision_tenant("acme", ACME_NAME, "admin@acme.test", "pw-acme-123")
            globex = provision_tenant("globex", GLOBEX_NAME, "admin@globex.test", "pw-globex-123")
            acme_id, globex_id = acme.id, globex.id

        print(f"\nprovisioned acme (id={acme_id}) and globex (id={globex_id})")

        def send_for(tenant_id, email):
            """Run the real send path for one hotel and return the captured mail."""
            captured.clear()
            with application.test_request_context():
                with tenant_context(tenant_id):
                    user = db.query(User).filter_by(email=email).first()
                    EmailService(db).send_email_verification_otp(user)
            return captured[-1] if captured else None

        def set_brand(tenant_id, value):
            with application.test_request_context():
                with tenant_context(tenant_id):
                    row = (
                        db.query(SystemSetting)
                        .filter_by(key="company_name")
                        .first()
                    )
                    row.value = value
                    db.commit()

        print("\n[1] the brand defaults to the hotel's own name")
        with application.app_context():
            with tenant_context(acme_id):
                check("acme's company_name defaults to 'Acme Hotel'",
                      get_tenant_setting(db, "company_name") == ACME_NAME,
                      get_tenant_setting(db, "company_name"))
            with tenant_context(globex_id):
                check("globex's company_name defaults to 'Globex Hotel'",
                      get_tenant_setting(db, "company_name") == GLOBEX_NAME,
                      get_tenant_setting(db, "company_name"))

        print("\n[2] a fresh hotel's mail is branded with its own name")
        mail = send_for(acme_id, "admin@acme.test")
        check("acme's mail is sent", mail is not None)
        check("acme's mail names Acme Hotel", mail and ACME_NAME in mail["html"])
        check("acme's mail does not fall back to the product name",
              mail and PRODUCT_FALLBACK not in mail["html"])

        print("\n[3] the brand comes from the setting, not the tenant row")
        set_brand(acme_id, ACME_BRAND)
        set_brand(globex_id, GLOBEX_BRAND)

        acme_mail = send_for(acme_id, "admin@acme.test")
        globex_mail = send_for(globex_id, "admin@globex.test")

        check("acme's mail shows the new brand", acme_mail and ACME_BRAND in acme_mail["html"])
        check("globex's mail shows its own brand", globex_mail and GLOBEX_BRAND in globex_mail["html"])
        check("acme's mail does not show globex's brand",
              acme_mail and GLOBEX_BRAND not in acme_mail["html"])
        check("globex's mail does not show acme's brand",
              globex_mail and ACME_BRAND not in globex_mail["html"])
        check("the two hotels' mail differs",
              acme_mail and globex_mail and acme_mail["html"] != globex_mail["html"])
        check("neither mail falls back to the product name",
              acme_mail and globex_mail
              and PRODUCT_FALLBACK not in acme_mail["html"]
              and PRODUCT_FALLBACK not in globex_mail["html"])

        print("\n[4] the public tenant-info endpoint serves per-hotel branding")
        client = application.test_client()

        acme_info = client.get("/api/v1/common/tenant-info", headers={"X-Tenant": "acme"})
        check("tenant-info returns 200", acme_info.status_code == 200,
              acme_info.get_data(as_text=True)[:300])
        acme_branding = ((acme_info.get_json(silent=True) or {}).get("data") or {}).get("branding") or {}
        check("acme's display name is its brand", acme_branding.get("display_name") == ACME_BRAND,
              acme_branding)

        globex_info = client.get("/api/v1/common/tenant-info", headers={"X-Tenant": "globex"})
        globex_branding = ((globex_info.get_json(silent=True) or {}).get("data") or {}).get("branding") or {}
        check("globex's display name is its own brand", globex_branding.get("display_name") == GLOBEX_BRAND,
              globex_branding)
        check("the branding blocks differ", acme_branding != globex_branding)

        check("an unknown tenant is not served",
              client.get("/api/v1/common/tenant-info", headers={"X-Tenant": "nope"}).status_code == 404)

        print("\n[5] seeded content is the hotel's, not the product's")
        with application.app_context():
            with tenant_context(acme_id):
                acme_titles = [s.title for s in db.query(LoginSliders).all()]
                check("acme's welcome slide names the hotel",
                      any(ACME_NAME in t for t in acme_titles), acme_titles)
            with tenant_context(globex_id):
                globex_titles = [s.title for s in db.query(LoginSliders).all()]
                check("globex's welcome slide names its own hotel",
                      any(GLOBEX_NAME in t for t in globex_titles), globex_titles)
                check("globex's slides do not name acme",
                      not any(ACME_NAME in t for t in globex_titles), globex_titles)

        print("\n[6] self-registration grants GUEST, not SUPER_ADMIN")
        with application.app_context():
            with tenant_context(acme_id):
                guest = db.query(Role).filter_by(role_code="GUEST").first()
                super_admin = db.query(Role).filter_by(role_code="SUPER_ADMIN").first()
                check("acme has a seeded GUEST role", guest is not None)
                check("GUEST is not the first-seeded role",
                      guest is not None and super_admin is not None and guest.id != super_admin.id,
                      (guest.id if guest else None, super_admin.id if super_admin else None))
            with tenant_context(globex_id):
                check("globex has its own GUEST role",
                      db.query(Role).filter_by(role_code="GUEST").first() is not None)

        registered = client.post(
            "/api/v1/auth/register",
            json={"first_name": "Self", "last_name": "Signup",
                  "email": "selfsign@acme.test", "password": "pw-self-123"},
            headers={"X-Tenant": "acme"},
        )
        check("registration succeeds", registered.status_code == 201,
              registered.get_data(as_text=True)[:400])

        with application.app_context():
            with tenant_context(acme_id):
                new_user = db.query(User).filter_by(email="selfsign@acme.test").first()
                acme_guest = db.query(Role).filter_by(role_code="GUEST").first()
                acme_super = db.query(Role).filter_by(role_code="SUPER_ADMIN").first()
                check("the registered user exists", new_user is not None)
                check("the registered user is a GUEST",
                      new_user is not None and new_user.role_id == acme_guest.id,
                      (new_user.role_id if new_user else None, acme_guest.id))
                check("the registered user is NOT a SUPER_ADMIN",
                      new_user is not None and new_user.role_id != acme_super.id,
                      new_user.role_id if new_user else None)

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
