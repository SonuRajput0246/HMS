"""The two things every tenant-scoped seeder needs, and nothing else.

Not a seeder itself -- it has no data and opens no session. It is separate so
that the policy about *which tenant* lives in one readable place instead of
being restated, slightly differently, in nineteen files.

Deliberately not folded into `src.database.tenant_context`. That module answers
"what is the current tenant" for the whole application, request path included.
This one is the seeding layer's stricter question: "was I actually told, out
loud, which hotel to write into?"
"""
from src.database.tenant_context import current_tenant_id


class MissingTenantError(RuntimeError):
    """A tenant-scoped seeder was run without naming a tenant."""


def resolve_tenant_id(tenant_id: int | None = None) -> int:
    """The tenant a seeder should write for, or raise.

    Two sources, in order: an explicit `tenant_id=` argument, then the ambient
    context set by `tenant_context(...)`. The explicit argument wins so a caller
    can seed one tenant from inside a block scoped to another without that being
    ambiguous.

    Neither present is an error, not a default. Seeding into "whichever tenant
    is nearest" is precisely the failure this prevents, and it would be silent:
    the rows would insert cleanly and belong to the wrong hotel.
    """
    resolved = tenant_id if tenant_id is not None else current_tenant_id()
    if resolved is None:
        raise MissingTenantError(
            "This seeder writes tenant-scoped rows, so it has to be told which "
            "tenant. Pass tenant_id=..., or run it inside tenant_context(...)."
        )
    return resolved


def safe_error(error, limit: int = 300) -> str:
    """Error text that survives being printed on a cp1252 console.

    Windows consoles default to cp1252. MySQL puts non-ASCII characters in its
    error text, and `print()` then raises UnicodeEncodeError *while handling*
    the original error -- which replaces a useful message with a blank one, at
    exactly the moment it matters. Encoded through ASCII first so the worst case
    is a '?' rather than a lost traceback.
    """
    cleaned = str(error).encode("ascii", errors="replace").decode("ascii")
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")
