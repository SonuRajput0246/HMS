from typing import TYPE_CHECKING
from src.database.base_model import BaseModel
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.models.common.user_model import User

def _enum_values(enum_cls):
    """Return the enum *values* so the DB stores 'email' / 'in_app'."""
    return [member.value for member in enum_cls]


class Template(BaseModel):
    __tablename__ = 'message_templates'

    id: Mapped[int] = mapped_column(primary_key=True)

    ## -------- Identity --------
    ## `code` is the stable contract used by backend services
    ## (e.g. TemplateCode.EMAIL_VERIFICATION_OTP). Never change it on a seeded
    ## row -- the `is_system` guard in the CRUD service enforces that.
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    ## -------- Delivery Channel --------
    channel: Mapped[str] = mapped_column(String(30), nullable=True)

    ## -------- Content --------
    ## For channel='email' only. Plain text with {{ variable }} placeholders.
    subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    ## For channel='in_app' only. Short single-line heading.
    title_template: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ## Required for both channels. Holds an HTML *fragment* for email
    ## (wrapped by templates/emails/layout.html at render time) and plain text
    ## for in_app. Must NOT contain a <html>/<body> wrapper.
    message_template: Mapped[str] = mapped_column(Text, nullable=False)

    ## -------- Editor Support --------
    ## Allowed placeholder names for this template, e.g. ["user_name", "otp"].
    ## Used by the CRUD API to validate admin input and by the Angular editor
    ## to offer an insert-variable helper plus a live preview.
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)

    ## Mock values used to render the preview, e.g. {"user_name": "John Doe"}.
    sample_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ## -------- Behaviour --------
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ## Seeded rows. The CRUD service blocks changes to `code` / `channel` and
    ## blocks deletion when this is True, so an admin cannot break the auth
    ## flows by renaming PASSWORD_RESET_OTP.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ## Bumped on every update. Enables optimistic locking and gives a simple
    ## "last edited" indicator in the UI.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    ## Ordering for the in-app notification list and the admin dropdown.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    ## -------- Audit (nullable: seeded rows have no acting user) --------
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )


    ## Relationships
    ## `foreign_keys` is required because both columns point at users.id,
    ## which would otherwise leave SQLAlchemy unable to pick a join condition.
    created_by_user: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    updated_by_user: Mapped["User | None"] = relationship(foreign_keys=[updated_by])


    ## CONSTRAINTS & INDEXES
    ##
    ## NOTE: there is deliberately NO unique constraint on (code, channel).
    ## MySQL does not support partial indexes, so a UNIQUE here would also cover
    ## soft-deleted rows and make it impossible to re-create a template with the
    ## same code after deleting it. (Note the existing `postgresql_where=` usage
    ## in services_model.py / folio_model.py is silently ignored on MySQL and
    ## behaves as a plain UNIQUE -- do not copy that pattern.)
    ## Uniqueness among live rows is enforced in the CRUD service, which returns
    ## 409 on conflict, matching upsert_role in admin_service.py.
    __table_args__ = (
        ## 1. Template lookup for a send action (code + channel + active)
        Index(
            "ix_template_resolve",
            "is_deleted",
            "channel",
            "code",
            "is_active"
        ),

        ## 2. Channel filter in the admin list grid
        Index(
            "ix_template_channel_list",
            "is_deleted",
            "channel",
            "id"
        ),

        ## 3. Prefix search on code
        Index(
            "ix_template_code_search",
            "is_deleted",
            "code"
        ),

        ## 4. Prefix search on name
        Index(
            "ix_template_name_search",
            "is_deleted",
            "name"
        ),

        ## 5. Duplicate (code, channel) pre-check -- deliberately NON-unique
        Index(
            "ix_template_code_channel_dup_check",
            "is_deleted",
            "code",
            "channel"
        ),
    )

    def __repr__(self):
        return f"Template(id={self.id}, code='{self.code}', channel='{self.channel.value}')"


    ### HELPERS

    def activate(self) -> None:
        """Mark the template usable for sending."""
        self.is_active = True

    def deactivate(self) -> None:
        """Stop the template from being used, without deleting it."""
        self.is_active = False

    def soft_delete(self) -> None:
        """Flag the row deleted. `deleted_at` is stamped by the service."""
        self.is_deleted = True

    def can_be_deleted(self) -> bool:
        """Seeded templates must stay in place -- services reference them by code."""
        return not self.is_system

    def can_change_identity(self) -> bool:
        """`code` and `channel` form the contract used by backend services."""
        return not self.is_system

    def is_email(self) -> bool:
        return self.channel == "email"

    def is_in_app(self) -> bool:
        return self.channel == "in_app"

    def is_resendable(self) -> bool:
        """Whether this row may be picked up by a send action."""
        return self.is_active and not self.is_deleted

    def get_allowed_variables(self) -> list[str]:
        return list(self.variables or [])

    def get_sample_context(self) -> dict:
        return dict(self.sample_context or {})

    def get_identity(self) -> tuple[str, str]:
        return (self.code, self.channel.value)