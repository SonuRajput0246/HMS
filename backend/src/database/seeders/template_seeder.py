"""Seeds the DB-driven template store.

Replaces the hardcoded Jinja files that used to live in
templates/emails/{email_verification,account_activation,password_reset}.html.
The copy below is ported verbatim from those three files, including the inline
styling, so switching to this store changes nothing an end user sees. The outer
<!DOCTYPE html>/600px-table boilerplate those files repeated is now the single
static templates/emails/layout.html.

Three codes, email channel only = three rows.

The three OTP flows are EMAIL-ONLY by design. An OTP is a possession factor
delivered to an address the user already controls, so an in-app counterpart
would only ever be reachable by someone already signed in -- who does not need
the code in the first place.

`channel='in_app'` remains fully supported for future notification templates;
this seeder just ships none, so `title_template` is unused here.

Each row is marked `is_system=True`, which makes the CRUD API refuse to change
its `code` or `channel` and refuse to delete it. Backend services resolve
templates by code, so a seeded row losing its identity would silently break the
flow it drives. The admin UI can still edit the name, subject, and body.

Runs against an empty table *for one tenant*. The existence check is by
(tenant_id, code, channel) with `is_deleted=False`, so it is safe to run per
tenant, and a row an admin has since edited is left alone rather than
overwritten. This is now a tenant default: `provision_tenant` calls it for
every new hotel, and each hotel owns its own copy of the three rows.
"""
from sqlalchemy import select

from src.api.models.template_model import Template
from src.api.utils.template_codes import (
    OTP_VARIABLES,
    TemplateCode,
    default_sort_order,
)
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from datetime import datetime, timezone


## Values used to render the live preview in the admin UI. Also what a reviewer
## sees on a fresh install, so keep them obviously placeholder-like.
SAMPLE_CONTEXT = {
    "user_name": "John Doe",
    "otp": "123456",
    "expiry_minutes": 10,
}

## The inline-styled OTP block, copied as-is from the original templates.
EMAIL_OTP_BLOCK = (
    '<p style="font-size: 24px; font-weight: bold; letter-spacing: 4px; '
    'text-align: center; color: #2c3e50;">{{ otp }}</p>'
)

## Shared email body. Every original template used this identical wording.
## The sign-off is the hotel's brand, not a fixed product name, so two hotels'
## copies of the same seeded template mail out under their own names.
EMAIL_BODY_TAIL = (
    "<p>This OTP is valid for <b>{{ expiry_minutes }} minutes</b>.</p>"
    "<p>If you did not request this, please ignore this email.</p>"
    "<br>"
    "<p>Regards,<br><b>{{ company_name }}</b></p>"
)


def _email_message(heading):
    return (
        f'<h2 style="color:#333;">{heading}</h2>'
        "<p>Hello {{ user_name }},</p>"
        "<p>Your One-Time Password (OTP) is:</p>"
        f"{EMAIL_OTP_BLOCK}"
        f"{EMAIL_BODY_TAIL}"
    )


templates_data = [
    ## ---------------- EMAIL VERIFICATION ----------------
    {
        "code": TemplateCode.EMAIL_VERIFICATION_OTP.value,
        "channel": "email",
        "name": "Email Verification OTP",
        "description": (
            "Sent when a user registers, and again if they request a new "
            "verification code from the login screen."
        ),
        ## Subject preserved exactly as the previous hardcoded value.
        "subject_template": "User email verification",
        "title_template": None,
        "message_template": _email_message("Verify Your Email"),
    },

    ## ---------------- ACCOUNT ACTIVATION ----------------
    {
        "code": TemplateCode.ACCOUNT_ACTIVATION_OTP.value,
        "channel": "email",
        "name": "Account Activation OTP",
        "description": (
            "Sent when a deactivated user reactivates their account."
        ),
        "subject_template": "Account activation OTP",
        "title_template": None,
        "message_template": _email_message("Activate your account."),
    },

    ## ---------------- PASSWORD RESET ----------------
    {
        "code": TemplateCode.PASSWORD_RESET_OTP.value,
        "channel": "email",
        "name": "Password Reset OTP",
        "description": (
            "Sent from the forgot-password flow and from the re-authentication "
            "prompt for a deactivated account."
        ),
        "subject_template": "Password reset OTP",
        "title_template": None,
        "message_template": _email_message("Reset Your Password"),
    },
]


def seed_templates(tenant_id: int | None = None):
    """Insert any missing template row for this tenant. Safe to call again."""
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        now = datetime.now(timezone.utc)
        created = 0
        skipped = 0

        for td in templates_data:
            ## tenant_id is part of the lookup: two hotels both need an
            ## EMAIL_VERIFICATION_OTP, and an unscoped check would hand the
            ## second hotel the first hotel's row -- meaning an admin editing
            ## their own welcome email would be editing a competitor's.
            stmt = select(Template).filter_by(
                tenant_id=tenant_id,
                code=td["code"],
                channel=td["channel"],
                is_deleted=False,
            )
            exists = db_session.execute(stmt).scalar_one_or_none()

            if exists:
                skipped += 1
                continue

            new_template = Template(
                tenant_id=tenant_id,
                code=td["code"],
                channel=td["channel"],
                name=td["name"],
                description=td["description"],
                subject_template=td["subject_template"],
                title_template=td["title_template"],
                message_template=td["message_template"],
                variables=list(OTP_VARIABLES),
                sample_context=dict(SAMPLE_CONTEXT),
                is_active=True,
                is_system=True,
                version=1,
                sort_order=default_sort_order(td["code"]),
                ## No acting user: seed rows are authored by the seeder.
                created_by=None,
                updated_by=None,
                is_deleted=False,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
            db_session.add(new_template)
            created += 1

        db_session.commit()
        print(
            f"--- Templates seeded successfully "
            f"({created} created, {skipped} already present). ---"
        )

    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding templates:", safe_error(e))
        ## A hotel with no OTP templates cannot verify an email or reset a
        ## password, so this must fail the provision rather than pass quietly.
        raise

    finally:
        ## Return the connection to the pool
        db_session.remove()


if __name__ == "__main__":
    seed_templates()
