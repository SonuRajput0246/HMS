"""Runs a .sql dump against the current session.

Two things this exists to get right, both of which the original per-file
loaders got wrong.

1. INSERT IGNORE, so a dump can be loaded more than once.
   currencies.sql is a bare `INSERT INTO currencies (code, name, symbol)
   VALUES (...)`. Re-running it raises 1062 Duplicate entry on the primary
   key, which aborts the whole file. IGNORE demotes duplicate-key (and
   foreign-key) errors to warnings, so the rows that already exist are
   skipped and the rest load. That makes `seed_*` idempotent, which is what
   lets it be re-run on an already-seeded database.

   IGNORE is applied to INSERT only. It must never reach a CREATE or ALTER:
   there, an ignored error means a table silently does not exist.

2. Errors are raised, never printed-and-returned.
   The old loaders caught, printed, and fell out of the function, so the
   orchestrator went on to report success while currencies, states and
   cities had not loaded. Every downstream failure then pointed at the wrong
   seeder -- a guest insert failed on a city foreign key three steps after
   the real cause.

   The message is truncated to ASCII before printing because Windows consoles
   default to cp1252. MySQL puts non-ASCII characters in its error text, and
   `print()` then raises UnicodeEncodeError *while handling* the original
   error, replacing a useful message with a blank one.
"""
import re

from sqlalchemy import text

from src.database.session import db_session

_INSERT = re.compile(r"^\s*INSERT\s+INTO\b", re.IGNORECASE)


def _safe_message(error, limit: int = 300) -> str:
    """Error text that is safe to print on a cp1252 console."""
    raw = str(error)
    cleaned = raw.encode("ascii", errors="replace").decode("ascii")
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def load_statement_file(file_path: str) -> int:
    """Execute every statement in `file_path`. Returns the statement count.

    Statements span many lines, so they accumulate until the `;` terminator
    rather than being split per line.
    """
    statement = ""
    executed = 0

    with open(file_path, "r", encoding="utf-8") as file:
        for raw in file:
            line = raw.strip()

            if not line or line.startswith("--"):
                continue

            statement += line + " "

            if not line.endswith(";"):
                continue

            if _INSERT.match(statement):
                statement = _INSERT.sub("INSERT IGNORE INTO", statement, count=1)

            db_session.execute(text(statement))
            executed += 1
            statement = ""

    if statement.strip():
        # A trailing fragment means the dump is truncated or malformed.
        # Silently ignoring it would leave tables quietly half-loaded.
        raise ValueError(
            f"{file_path} ends with an unterminated statement "
            f"(missing ';') after {executed} statements: {statement[:80]!r}"
        )

    return executed


def run_sql_seeder(label: str, file_path: str, success_message: str) -> int:
    """Load a dump, committing on success and raising on failure."""
    try:
        executed = load_statement_file(file_path)
        db_session.commit()
        print(f"--- {success_message} ({executed} statements) ---")
        return executed

    except Exception as e:
        db_session.rollback()
        print(f"!!! {label} FAILED: {_safe_message(e)}")
        # Re-raise. See module docstring: swallowing this made a total
        # failure look like a successful seed.
        raise