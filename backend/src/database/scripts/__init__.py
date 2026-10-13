"""Database maintenance scripts.

`create_databases` -- creates the per-instance databases.
`dedupe_users`     -- removes duplicate super admin rows from an older
                      seeding bug that inserted one per run.

Nothing here is imported by the application. These are run explicitly.
"""