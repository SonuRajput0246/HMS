"""Every module name that appears in any instance's module seeder.

Read from the seeder modules rather than restated here, so this cannot drift
out of step with them. Used by audit_authorization.py to tell a typo in a
requires_module() call apart from a database that holds another instance's
module set -- a distinction that decides whether the fix is a code change or a
seed run.
"""
import importlib


def known_module_names():
    names = set()
    for path in (
        "src.database.seeders.hms.module_seeder",
        "src.database.seeders.cms.module_seeder",
    ):
        try:
            module = importlib.import_module(path)
        except Exception:
            continue
        for value in vars(module).values():
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and "module_name" in entry:
                        names.add(entry["module_name"])
    return names


if __name__ == "__main__":
    for name in sorted(known_module_names()):
        print(name)