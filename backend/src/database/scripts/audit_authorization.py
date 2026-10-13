"""Deny-by-default audit: does every authenticated route declare a module?

The authorization model in src/api/middlewares/authorization.py is deny by
default -- a route is reachable only if it says which module it needs. That is
only a real guarantee if the coverage is complete, and completeness is exactly
the sort of thing that decays as routes are added. So it is checked rather than
assumed.

Three kinds of route are distinguished:

  declared      wrapped in requires_module(name)        -- fine
  self-service  wrapped in requires_module(SELF_SERVICE) -- fine, and explicit
  UNDECLARED    wrapped in bare jwt_required            -- a hole
  public        neither marker                           -- fine

An UNDECLARED route is authenticated but carries no module requirement, which
means any signed-in account reaches it regardless of role. That was 19 of 19
endpoints in the Phase 10 probe.

Run it with --apply to list routes that still need annotating. Read-only by
default, like prune_modules.py.

    python -m src.database.scripts.audit_authorization
    python -m src.database.scripts.audit_authorization --apply
"""
import argparse
import os
import sys

os.environ.setdefault("INSTANCE_TYPE", "CMS")

import app as flask_app  # noqa: E402
from sqlalchemy import select  # noqa: E402

from src.api.models.common.module_model import Module  # noqa: E402
from src.database.scripts.known_modules import known_module_names  # noqa: E402
from src.database.session import db_session  # noqa: E402


def classify(application):
    declared, self_service, undeclared, public = [], [], [], []

    for rule in application.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        view = application.view_functions.get(rule.endpoint)
        module = getattr(view, "__required_module__", None)
        auth_only = getattr(view, "__auth_only__", False)

        entry = (rule.endpoint, sorted(rule.methods - {"HEAD", "OPTIONS"}))

        if module is not None:
            if module == "__self_service__":
                self_service.append(entry)
            else:
                declared.append((module,) + entry)
        elif auth_only:
            undeclared.append(entry)
        else:
            public.append(entry)

    return declared, self_service, undeclared, public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="list the undeclared routes in detail")
    args = parser.parse_args()

    instance = os.environ.get("INSTANCE_TYPE", "CMS")
    application = flask_app.create_app()

    declared, self_service, undeclared, public = classify(application)

    ## Every module name a route names must exist in this instance's tree. A
    ## typo would otherwise 403 everybody, the super admin included, and it
    ## would do so silently -- nothing else in the system would say why.
    tree = {
        row.module_name
        for row in db_session.execute(
            select(Module.module_name).filter(
                Module.is_active == True, Module.is_deleted == False
            )
        ).all()
    }
    named = sorted({module for module, _e, _m in declared})
    unknown = [m for m in named if m not in tree]

    by_module = {}
    for module, endpoint, methods in declared:
        by_module.setdefault(module, []).append(f"{','.join(methods):22} {endpoint}")

    print(f"instance: {instance}")
    print("=" * 72)
    print(f"module tree rows      : {len(tree)}")
    print(f"declared routes       : {len(declared)}")
    print(f"self-service routes   : {len(self_service)}   (valid session, no module)")
    print(f"public routes         : {len(public)}")
    print(f"UNDECLARED routes     : {len(undeclared)}")
    print(f"unknown module names  : {len(unknown)}"
          + (f"   {unknown}" if unknown else ""))
    print("=" * 72)

    for module in sorted(by_module):
        entries = sorted(by_module[module])
        print(f"\n  {module}  ({len(entries)})")
        for line in entries:
            print(f"      {line}")

    print("\n  self-service")
    for endpoint, methods in sorted(self_service):
        print(f"      {','.join(methods):22} {endpoint}")

    if undeclared:
        print("\n" + "!" * 72)
        print("UNDECLARED -- reachable by any signed-in account, whatever their role")
        print("!" * 72)
        for endpoint, methods in sorted(undeclared):
            print(f"  {','.join(methods):22} {endpoint}")
        print()
        print("Each needs either")
        print('    requires_module("MODULE")(view)      -- for a business module')
        print("    requires_module(SELF_SERVICE)(view)  -- only needs a valid session")
        if not args.apply:
            print("\nDry run. Nothing written.")
        return 1

    if unknown:
        print("\n" + "!" * 72)
        print("ROUTES NAME MODULES THAT DO NOT EXIST IN THIS INSTANCE")
        print("!" * 72)
        for name in unknown:
            print(f"  {name}")
        print()
        print("These would 403 every caller, super admin included, because no")
        print("role holds a row for a module that is not in the tree.")
        print()
        ## Distinguish "someone typo'd a module name" from "the database holds
        ## another instance's module set". The second is the documented
        ## shared-database problem and needs a seed run, not a code change --
        ## telling them apart here saves a long hunt.
        every_known = known_module_names()
        if set(unknown) <= every_known - tree:
            print("Each is a real module of some instance, just not this one, so")
            print("the database is holding another instance's module set.")
            print(f"  tree here: {sorted(tree)}")
            print(f"  all known: {sorted(every_known)}")
            print()
            print("Fix by seeding this instance, not by editing code:")
            print(f"  INSTANCE_TYPE={instance} python -m src.database.seeders.run_base_seeders")
        else:
            stray = sorted(set(unknown) - every_known)
            print(f"At least one is not a module name in any seeder: {stray}")
            print("That one is a typo in a requires_module() call.")
        if not args.apply:
            print("\nDry run. Nothing written.")
        return 1

    print("\nAll authenticated routes declare a module requirement,")
    print("and every module they name exists in this instance's tree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())