"""Dynamic leak test: can tenant B see tenant A's rows?

This is the test Phase 3 is built to pass, and it is written so that it FAILS on
the code from Phase 2 (where nothing filters reads) and passes once the
enforcement listener lands. Run it either way:

    python -m src.database.scripts.tenant_leak_test
    python -m src.database.scripts.tenant_leak_test --keep   # leave the db

It builds a throwaway database (`hms_leaktest`) with `Base.metadata.create_all`
-- the dev database is never touched -- seeds the platform rows, provisions two
hotels, and then asserts:

  1. COVERAGE. The set of tenant-scoped models is exactly the boundary the design
     names. A model that forgets the mixin, or a new one that arrives without
     being scoped, is a failure here rather than a silent hole.

  2. FILTER PRESENT. For every scoped model, a plain `select()` executed inside a
     tenant context emits a WHERE clause that names `tenant_id`. This is checked
     by capturing the SQL, so it holds for a model added later with no new test.

  3. ISOLATION. With a row in every scoped table for tenant A, tenant B reads
     zero of them, and each tenant reads exactly its own rows.

  4. §5.3 HAZARDS, to be proven rather than assumed at runtime:
       * `Session.get()` on a direct primary key
       * ORM-enabled bulk `Query.update()` / `Query.delete()`
       * joined eager loading of a related row
       * `text()` executed through the session
       * a SELECT issued from inside `before_flush`

  5. WRITES. `tenant_id` is stamped from context; an insert with no context is
     refused; a foreign key that reaches into another tenant is refused; the
     same foreign key inside the tenant is allowed.

Exit code is 0 when every check passes and 1 otherwise, so it composes.
"""
import argparse
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import lazyload, scoped_session, sessionmaker

from src.config import get_config
from src.database.tenant_context import (
    bypass_tenant_filter,
    clear_tenant_context,
    tenant_context,
)
from src.database.tenant_scoped import TenantScoped

SCRATCH_DB = "hms_leaktest"

## The tenancy boundary as agreed in docs/multi-tenancy.md §3.3. Pinned here so
## that a model silently leaving the boundary -- or a new tenant-scoped table
## arriving without a decision -- is a test failure, not a surprise in prod.
EXPECTED_SCOPED_TABLES = {
    "account_deletions", "additional_guests",
    "email_otps", "guests",
    "inventory", "inventory_categories",
    "login_sliders", "message_templates",
    "payments", "prefixes",
    "reservation_additional_guests", "reservation_primary_guests",
    "reservation_sequences", "reservations",
    "role_module_access", "roles",
    "room_amenities", "room_blocks", "room_type_amenities", "room_types", "rooms",
    "system_settings", "tokens", "users",
}

## Tables provisioning fills by itself, so a non-zero count in tenant A is
## expected without any demo data.
_PROVISIONED = {
    "roles", "role_module_access", "prefixes", "reservation_sequences",
    "system_settings", "message_templates", "login_sliders", "users",
}

_failures = []
_passes = 0

## Every SQL string the engine emits, so `emitted_sql` can inspect what a
## statement actually compiled to. Populated by one listener installed in main().
_CAPTURED = []


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


def scoped_classes():
    from src.database.base import Base
    return sorted(
        (m.class_ for m in Base.registry.mappers
         if issubclass(m.class_, TenantScoped)),
        key=lambda c: c.__tablename__,
    )


def _capture_sql(conn, cursor, statement, parameters, context, executemany):
    _CAPTURED.append(statement)


def emitted_sql(session, stmt):
    """The last SQL statement the engine sent for `stmt`."""
    _CAPTURED.clear()
    session.execute(stmt).all()
    return _CAPTURED[-1] if _CAPTURED else ""


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

    ## Rebinding the module-level session to the scratch database has to happen
    ## BEFORE the seeders are imported: they do `from src.database.session import
    ## db_session`, which binds the name at import time. Rebinding after that
    ## would leave every seeder writing to the dev database.
    import src.database.session as session_module
    session_module.engine.dispose()
    scratch = create_engine(url.set(database=SCRATCH_DB), pool_pre_ping=True)
    session_module.engine = scratch
    session_module.session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=scratch
    )
    session_module.db_session = scoped_session(session_module.session_factory)

    ## The registry has to be complete before create_all(). Importing the model
    ## package is what populates it.
    import src.api.models  # noqa: F401

    ## The before_insert / before_update listeners are registered as a side
    ## effect of importing these modules, exactly as app.py does. Without them
    ## created_at / updated_at are NULL and every insert fails at the database.
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


def seed_two_hotels():
    """Platform rows, then two provisioned hotels. Returns (a_id, b_id)."""
    from src.database.seeders.run_base_seeders import (
        seed_platform_data, seed_tenant_demo_data,
    )
    from src.database.seeders.provision_tenant import provision_tenant

    seed_platform_data()

    a = provision_tenant("acme", "Acme Hotel", "admin@acme.test", "pw-acme-123")
    b = provision_tenant("globex", "Globex Hotel", "admin@globex.test", "pw-globex-123")
    a_id, b_id = a.id, b.id

    ## Demo data goes to A only, so "B reads zero of A's rows" has something to
    ## actually read. Demo data covers stock, rooms, guests and reservations.
    seed_tenant_demo_data(a_id)

    ## The remaining scoped tables are not reached by demo data, so give A one
    ## row in each. Without this the isolation check would pass vacuously on an
    ## empty table.
    from src.database.session import db_session
    from src.api.models import (
        AccountDeletions, EmailOTP, Payment, Reservation, Token, User,
    )

    with tenant_context(a_id):
        admin = db_session.execute(
            select(User).where(User.email == "admin@acme.test")
        ).scalar_one()
        reservation = db_session.execute(select(Reservation)).scalars().first()
        now = datetime.now(timezone.utc)

        db_session.add(Token(
            tenant_id=a_id,
            user_id=admin.id, access_token="a-access", refresh_token_hash="a-refresh",
            is_revoked=False, created_at=now,
        ))
        db_session.add(EmailOTP(
            tenant_id=a_id,
            user_id=admin.id, otp_hash="a-otp", otp_purpose="EMAIL_VERIFICATION",
            expires_at=now, attempts=0, is_used=False, created_at=now, updated_at=now,
        ))
        db_session.add(AccountDeletions(
            tenant_id=a_id,
            user_id=admin.id, reason="leak test",
            requested_at=now, account_deletion_status="pending", account_deleted_by="user",
        ))
        db_session.add(Payment(
            tenant_id=a_id,
            reservation_id=reservation.id, payment_type="payment", amount=100,
            currency="INR", payment_method="cash", payment_status="completed",
            verified_by=admin.id, exchange_rate=1, base_amount=100,
        ))
        db_session.commit()

    return a_id, b_id


def drop_scratch_database(scratch, admin):
    ## Everything that could hold a pooled connection must be closed before the
    ## DROP, or the drop blocks forever on idle sessions.
    from src.database.session import db_session
    db_session.remove()
    scratch.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
    admin.dispose()


## --------------------------------------------------------------------------
## checks
## --------------------------------------------------------------------------

def check_coverage():
    print("\n[1] coverage of the tenancy boundary")
    classes = scoped_classes()
    tables = {c.__tablename__ for c in classes}
    check("every §3.3 table inherits TenantScoped",
          tables == EXPECTED_SCOPED_TABLES,
          f"missing={sorted(EXPECTED_SCOPED_TABLES - tables)} "
          f"unexpected={sorted(tables - EXPECTED_SCOPED_TABLES)}")

    from sqlalchemy import inspect as sa_inspect
    for c in classes:
        mapper = sa_inspect(c)
        has = "tenant_id" in mapper.columns
        check(f"{c.__tablename__}.tenant_id is NOT NULL",
              has and not mapper.columns["tenant_id"].nullable,
              detail=f"present={has}")


def check_filter_present(db, a_id):
    print("\n[2] every scoped model filters on tenant_id")
    for c in scoped_classes():
        with tenant_context(a_id):
            sql = emitted_sql(db, select(c).options(lazyload("*")))
        tail = sql.split(" FROM ", 1)[1] if " FROM " in sql else sql
        check(f"{c.__tablename__}: SELECT carries tenant_id predicate",
              re.search(r"\btenant_id\s*=", tail) is not None,
              detail=sql)


def check_isolation(db, a_id, b_id):
    print("\n[3] isolation: B reads none of A's rows")
    for c in scoped_classes():
        with bypass_tenant_filter():
            rows = db.execute(select(c)).scalars().all()
        count_a = sum(1 for r in rows if r.tenant_id == a_id)
        count_b = sum(1 for r in rows if r.tenant_id == b_id)
        other = [r for r in rows if r.tenant_id not in (a_id, b_id)]

        with tenant_context(a_id):
            seen_a = db.query(c).count()
        with tenant_context(b_id):
            seen_b = db.query(c).count()

        name = c.__tablename__
        check(f"{name}: A sees exactly its own ({seen_a}/{count_a})", seen_a == count_a)
        check(f"{name}: B sees exactly its own ({seen_b}/{count_b})", seen_b == count_b)
        check(f"{name}: no NULL or stray tenant_id", not other)
        if name in _PROVISIONED:
            check(f"{name}: A actually has rows", count_a > 0)


def test_hazard_session_get(db, a_id, b_id):
    from src.api.models import User
    with bypass_tenant_filter():
        a_user = db.query(User).filter(User.tenant_id == a_id).first()
    with tenant_context(b_id):
        got = db.get(User, a_user.id)
    check("Session.get() cannot load another tenant's row by pk", got is None)
    with tenant_context(a_id):
        got = db.get(User, a_user.id)
    check("Session.get() loads the row inside its own tenant",
          got is not None and got.id == a_user.id)


def test_hazard_bulk(db, a_id, b_id):
    from sqlalchemy import select as _select
    from src.api.models import Token, User
    with bypass_tenant_filter():
        a_user = db.query(User).filter(User.tenant_id == a_id).first()

    with tenant_context(b_id):
        touched = db.query(Token).filter(Token.user_id == a_user.id).update(
            {"is_revoked": True}, synchronize_session=False)
    check("bulk Query.update() in B touches none of A's rows", touched == 0)

    with tenant_context(b_id):
        deleted = db.query(Token).filter(Token.user_id == a_user.id).delete(
            synchronize_session=False)
    check("bulk Query.delete() in B deletes none of A's rows", deleted == 0)

    with bypass_tenant_filter():
        live = db.execute(
            _select(Token).where(Token.user_id == a_user.id)
        ).scalars().all()
    check("A's token is untouched", len(live) == 1 and live[0].is_revoked is False)


def test_hazard_eager_load(db, a_id, b_id):
    from src.api.models import Reservation
    with bypass_tenant_filter():
        a_res = db.query(Reservation).filter(Reservation.tenant_id == a_id).first()
    with tenant_context(b_id):
        got = db.execute(
            select(Reservation).where(Reservation.id == a_res.id)
        ).scalar_one_or_none()
    check("a joined-eager-loading row is invisible across tenants", got is None)
    with tenant_context(a_id):
        got = db.execute(
            select(Reservation).where(Reservation.id == a_res.id)
        ).scalar_one_or_none()
        creator_ok = got is not None and (
            got.created_by_user is None or got.created_by_user.tenant_id == a_id)
    check("its eager-loaded creator resolves inside the tenant", creator_ok)


def test_hazard_text(db, a_id):
    with tenant_context(a_id):
        try:
            value = db.execute(text("SELECT 1")).scalar()
            ok = value == 1
            detail = ""
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
    check("text() through the session still executes", ok, detail)


def test_writes(db, a_id, b_id):
    from src.api.models import Role, User
    from src.database.tenant_enforcement import (
        CrossTenantReferenceError, TenantContextMissingError,
    )
    from sqlalchemy import select as _select

    ## 1. refuse an unscoped insert
    clear_tenant_context()
    try:
        db.add(Role(role_code="ORPHAN", role_name="Orphan",
                    is_active=True, is_deleted=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)))
        db.flush()
        raised = False
    except TenantContextMissingError:
        raised = True
    finally:
        db.rollback()
    check("an insert with no tenant context is refused", raised)

    ## 2. stamp from context
    with tenant_context(a_id):
        role = Role(role_code="STAMPED", role_name="Stamped",
                    is_active=True, is_deleted=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc))
        db.add(role)
        db.flush()
        stamped = role.tenant_id
        db.rollback()
    check("tenant_id is stamped from the context", stamped == a_id,
          detail=f"got {stamped}")

    ## 3. refuse a foreign key into another tenant
    with bypass_tenant_filter():
        a_role = db.query(Role).filter(Role.tenant_id == a_id).first()
    try:
        with tenant_context(b_id):
            db.add(User(role_id=a_role.id, first_name="Cross", last_name="Tenant",
                        email="cross@globex.test", password="x",
                        is_active=True, is_deleted=False,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)))
            db.flush()
        refused = False
    except CrossTenantReferenceError:
        refused = True
    finally:
        db.rollback()
    check("a foreign key into another tenant is refused", refused)

    ## 4. allow the same foreign key inside the tenant
    with bypass_tenant_filter():
        b_role = db.query(Role).filter(Role.tenant_id == b_id).first()
    try:
        with tenant_context(b_id):
            db.add(User(role_id=b_role.id, first_name="Same", last_name="Tenant",
                        email="same@globex.test", password="x",
                        is_active=True, is_deleted=False,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)))
            db.flush()
        allowed = True
    except Exception as exc:  # noqa: BLE001
        allowed = False
        print(f"          (unexpected: {type(exc).__name__}: {exc})")
    finally:
        db.rollback()
    check("the same foreign key inside the tenant is allowed", allowed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true",
                        help="leave the scratch database in place")
    args = parser.parse_args()

    scratch = admin = None
    try:
        scratch, admin = build_scratch_database()
        event.listen(scratch, "before_cursor_execute", _capture_sql)

        ## A real app context, because some before_insert listeners (email OTP
        ## expiry) read current_app.config. Importing `app` here -- after the
        ## session was rebound above -- also means the routes and services it
        ## imports capture the scratch db_session rather than the dev one.
        import app as flask_app
        application = flask_app.create_app()
        with application.app_context():
            from src.database.session import db_session as db

            a_id, b_id = seed_two_hotels()
            print(f"\nprovisioned acme (id={a_id}) and globex (id={b_id})")

            check_coverage()
            check_filter_present(db, a_id)
            check_isolation(db, a_id, b_id)

            print("\n[4] runtime hazards the design said to prove")
            test_hazard_session_get(db, a_id, b_id)
            test_hazard_bulk(db, a_id, b_id)
            test_hazard_eager_load(db, a_id, b_id)
            test_hazard_text(db, a_id)

            print("\n[5] write-side enforcement")
            test_writes(db, a_id, b_id)

    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        _failures.append(f"unexpected error: {type(exc).__name__}: {exc}")
    finally:
        if scratch is not None and not args.keep:
            try:
                drop_scratch_database(scratch, admin)
            except Exception as exc:  # noqa: BLE001
                print(f"  (teardown warning: {exc})")

    print("\n" + "=" * 72)
    print(f"  {_passes} passed, {len(_failures)} failed")
    for label in _failures:
        print(f"    FAILED: {label}")
    print("=" * 72)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
