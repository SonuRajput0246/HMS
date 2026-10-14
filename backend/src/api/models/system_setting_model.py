from src.database.base import Base
from src.database.tenant_scoped import TenantScoped
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class SystemSetting(Base, TenantScoped):
    """A per-hotel key/value setting.

    `key` alone can no longer be the primary key. Two hotels both need a
    `default_currency`, and a single-column key would let whoever seeded first
    block everyone else. The primary key is therefore (tenant_id, key): the pair
    is what is unique, and a key stays unique *within* a hotel -- which is the
    contract payment_service relies on when it resolves `default_currency` by
    key with scalar/first.

    `tenant_id` is redeclared here rather than inherited purely to add
    primary_key=True. The mixin's copy is a plain NOT NULL column, and a column
    that is not part of the key cannot be one. SQLAlchemy lets a class body
    override a mixin attribute, and the override is a throwaway: nothing else
    in this table's identity changed.
    """

    __tablename__ = "system_settings"

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))

    def __repr__(self):
        return f"SystemSetting(tenant_id={self.tenant_id}, Key={self.key}, Value={self.value})"
