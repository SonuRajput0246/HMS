"""fix user email check constraint rejecting dotted local parts

ck_user_email_format was:

    INSTR(email, '@') > 1 AND INSTR(email, '.') > INSTR(email, '@')

INSTR returns the FIRST occurrence of the substring, so the second comparison
only holds when the first dot in the address falls after the '@'. Any dot in
the local part -- first.last@gmail.com, j.smith@example.co.uk -- puts the
first dot before the '@' and fails.

Registration for those addresses returned 400 "An internal error occurred
during registration", because the marshmallow email field accepts them and the
insert is what the database rejects. The super admin seeder's own address
(sonurajput8454@gmail.com) has no dot and was unaffected, which is why seeded
data looked healthy.

The replacement keeps the intent -- an '@' with something either side, and a
dot in the domain -- without depending on where the first dot happens to be:

    email LIKE '_%@_%.__%'

which reads as: at least one character, '@', at least one character, '.', at
least two characters. That is a cheap structural check, not a full RFC 5322
parse; real validation stays where it belongs, in the schema layer.

Revision ID: a7f3c21d9b40
Revises: dc171fda68b9
"""
from alembic import op

revision = "a7f3c21d9b40"
down_revision = "dc171fda68b9"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_user_email_format", "users", type_="check")
    op.create_check_constraint(
        "ck_user_email_format",
        "users",
        "email LIKE '_%@_%.__%'",
    )


def downgrade():
    op.drop_constraint("ck_user_email_format", "users", type_="check")
    op.create_check_constraint(
        "ck_user_email_format",
        "users",
        "INSTR(email, '@') > 1 AND INSTR(email, '.') > INSTR(email, '@')",
    )