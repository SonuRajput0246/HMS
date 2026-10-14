"""Static audit: does anything reach a tenant-scoped table around the filter?

The runtime guard in src/database/tenant_enforcement.py covers every statement
that goes through the ORM. It cannot cover the statements that do not:

  * raw SQL -- `session.execute(text("SELECT ... FROM users"))` is a string; the
    filter never sees it.
  * a Core `update()` / `delete()` on a scoped table, as opposed to an ORM one --
    ORM statements get loader criteria, plain Core Table statements do not.
  * a connection pulled straight off the engine.
  * a model that carries `__tablename__` but was never put inside the boundary.
    The dynamic leak test catches a scoped model that filters nothing; this
    catches the mirror image, a table that is silently global.

`Session.get()` is listed too. It is identity-map-first, so it was the one read
path the ORM filter could miss -- that is now handled in the enforcement layer
by wrapping it, and the sites are listed so a future change is visible.

Read-only. Run it anywhere; it needs no database.

    python -m src.database.scripts.tenant_leak_audit
    python -m src.database.scripts.tenant_leak_audit --list   # show every site

Exit code is 0 when every table is accounted for and no unwrapped data path
exists, 1 otherwise.
"""
import argparse
import re
import sys
from pathlib import Path

import src.api.models  # noqa: F401  (populate the registry)
from src.database.base import Base
from src.database.tenant_scoped import TenantScoped

## §3.1 of docs/multi-tenancy.md: shared reference data every tenant reads.
GLOBAL_TABLES = {
    "countries", "states", "cities", "currencies",
    "modules", "enum_definitions", "enum_options", "inventory_units",
}

## §3.2: above every tenant, so they cannot carry a tenant_id.
PLATFORM_TABLES = {"tenants", "platform_users"}

NON_SCOPED = GLOBAL_TABLES | PLATFORM_TABLES

SRC = Path(__file__).resolve().parents[2]          # backend/src
SKIP_DIRS = {"migrations", "__pycache__"}
## Seeders load .sql dumps for the *global* tables (countries, cities, ...) with
## raw SQL on purpose, and the dev scripts are throwaway. Neither is a hole.
RAW_SQL_ALLOWED_DIRS = {"seeders", "scripts"}

RAW_SQL = re.compile(r"\.execute\(\s*(?:sa\.|sqlalchemy\.)?text\(")
RAW_CONNECTION = re.compile(r"\.connection\(")
CORE_DML = re.compile(r"\.execute\(\s*(?:sa\.|sqlalchemy\.)?(?:update|delete)\(")
BYPASS = re.compile(r"bypass_tenant_filter\s*\(")
SKIP = re.compile(r"skip_tenant_filter")
SESSION_GET = re.compile(r"\.get\(\s*[A-Z]\w*\s*,")


def scoped_and_all_tables():
    all_tables = {m.class_.__tablename__ for m in Base.registry.mappers}
    scoped = {m.class_.__tablename__ for m in Base.registry.mappers
              if issubclass(m.class_, TenantScoped)}
    return scoped, all_tables


def python_files():
    for path in SRC.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def scan(patterns):
    """Return {label: [(path, lineno, text)]} for every match in src/."""
    hits = {label: [] for label, _ in patterns}
    for path in python_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(SRC).as_posix()
        for lineno, line in enumerate(lines, 1):
            for label, pattern in patterns:
                if pattern.search(line):
                    hits[label].append((relative, lineno, line.strip()))
    return hits


def under(directory, relative_path):
    return directory in relative_path.split("/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true",
                        help="print every site, not just the summary")
    args = parser.parse_args()

    holes = []

    print("=" * 72)
    print("  tenant leak audit")
    print("=" * 72)

    ## -- 1. every table is either inside the boundary or named as global -------
    scoped, all_tables = scoped_and_all_tables()
    unaccounted = sorted(all_tables - scoped - NON_SCOPED)
    stray_scope = sorted(scoped & NON_SCOPED)
    print(f"\n[1] tables")
    print(f"    tenant-scoped : {len(scoped)}")
    print(f"    global        : {len(GLOBAL_TABLES)}")
    print(f"    platform      : {len(PLATFORM_TABLES)}")
    print(f"    total mapped  : {len(all_tables)}")
    if unaccounted:
        holes.append(f"{len(unaccounted)} table(s) are neither scoped nor declared global")
        print(f"    UNACCOUNTED   : {unaccounted}")
        print("        Each is a table that exists with no tenancy decision. Either")
        print("        inherit TenantScoped or add it to GLOBAL_TABLES with a reason.")
    if stray_scope:
        holes.append("a global/platform table also inherits TenantScoped")
        print(f"    ALSO SCOPED   : {stray_scope}")

    ## -- 2. statements the ORM filter cannot see ------------------------------
    hits = scan([
        ("raw SQL through the session", RAW_SQL),
        ("connection pulled off the engine", RAW_CONNECTION),
        ("Core UPDATE/DELETE through the session", CORE_DML),
    ])

    print(f"\n[2] data paths the ORM filter cannot wrap")
    for label, found in hits.items():
        if label == "raw SQL through the session":
            ## Allowed for the .sql-dump loaders, which only ever touch global
            ## tables. Anywhere else it is unwrapped SQL.
            offending = [h for h in found if not under("seeders", h[0])
                         and not under("scripts", h[0])]
        else:
            offending = [h for h in found if not under("scripts", h[0])]
        status = "OK" if not offending else "HOLE"
        print(f"    {status:5} {label}: {len(found)} site(s)"
              + (f", {len(offending)} outside the allowlist" if offending else ""))
        if offending:
            holes.append(f"{label}: {len(offending)} site(s) outside the allowlist")
            for path, lineno, text in offending:
                print(f"            {path}:{lineno}  {text}")
        elif args.list:
            for path, lineno, text in found:
                print(f"            {path}:{lineno}  {text}")

    ## -- 3. the deliberate escape hatches, for visibility ---------------------
    hatches = scan([
        ("bypass_tenant_filter()", BYPASS),
        ("skip_tenant_filter", SKIP),
        ("Session.get()", SESSION_GET),
    ])
    print(f"\n[3] escape hatches (informational)")
    for label, found in hatches.items():
        print(f"    {label}: {len(found)} site(s)")
        for path, lineno, text in found:
            print(f"            {path}:{lineno}  {text}")

    print("\n" + "=" * 72)
    if holes:
        print(f"  {len(holes)} HOLE(S)")
        for hole in holes:
            print(f"    - {hole}")
        print("=" * 72)
        return 1
    print("  clean: every table is accounted for and every ORM read is wrapped")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
