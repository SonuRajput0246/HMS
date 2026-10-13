"""Database maintenance scripts.

`dedupe_users`          -- removes duplicate super admin rows from an older
                           seeding bug that inserted one per run.
`audit_authorization`   -- checks every authenticated route declares a module.

Nothing here is imported by the application. These are run explicitly.
"""