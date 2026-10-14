"""Per-hotel settings: the defaults a hotel starts with, and how to read them.

`system_settings` is a per-tenant key/value table (primary key
`(tenant_id, key)`). Every read is scoped to the current tenant by the Phase 3
`do_orm_execute` filter, so a caller does not have to remember to filter -- but
these helpers still require a tenant, because a missing scope would otherwise
let a plain `.all()` merge every hotel's rows into one dict keyed only by key.

Two callers share this module so their idea of "the defaults" cannot drift:

  * `system_setting_seeder` writes them when a hotel is provisioned.
  * the send path (email branding) and the public `tenant-info` endpoint read
    them.

`company_name` is the one default that is not really a constant: the seeder
resolves it to the hotel's own display name. `DEFAULT_COMPANY_NAME` is the
last-resort value for a hotel whose row is somehow absent, not the intended
brand.
"""
from src.api.models.system_setting_model import SystemSetting
from src.database.tenant_context import current_tenant_id


## Last-resort brand name. A provisioned hotel overrides this with its own
## `company_name` row; this is only what an unprovisioned or half-seeded tenant
## falls back to.
DEFAULT_COMPANY_NAME = "HMS"


## Every key a hotel is seeded with, and the value used when the row is absent.
## Keep in step with `system_setting_seeder`; it imports this dict rather than
## restating it, so the two cannot disagree.
DEFAULT_SETTINGS: dict[str, str] = {
    "default_currency": "INR",
    "company_name": DEFAULT_COMPANY_NAME,
    "app_logo_image": "",
    "terms_condition_url": "",
    "privacy_policy_url": "",
}


## The subset of settings a login page is allowed to display. Deliberately
## narrow: nothing here is anonymous business beyond how the hotel is branded.
BRANDING_KEYS: tuple[str, ...] = (
    "company_name",
    "app_logo_image",
    "terms_condition_url",
    "privacy_policy_url",
)


def get_tenant_setting(db, key, tenant_id=None, default=None):
    """One setting for a tenant, or its default.

    `tenant_id` defaults to the ambient scope. A missing row, or no scope at
    all, falls back to `DEFAULT_SETTINGS[key]` and then `default` rather than
    raising: a read on the send path must never be the reason a login fails.
    """
    tenant_id = tenant_id if tenant_id is not None else current_tenant_id()
    if tenant_id is None:
        return DEFAULT_SETTINGS.get(key, default)

    row = (
        db.query(SystemSetting)
        .filter(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == key,
        )
        .first()
    )
    if row is not None:
        return row.value

    return DEFAULT_SETTINGS.get(key, default)


def get_tenant_branding(db, tenant_id=None) -> dict:
    """The branding subset for a tenant, with defaults applied.

    One query for all four keys, because the public tenant-info endpoint reads
    every one of them on each login page load.
    """
    tenant_id = tenant_id if tenant_id is not None else current_tenant_id()
    if tenant_id is None:
        return {key: DEFAULT_SETTINGS[key] for key in BRANDING_KEYS}

    rows = (
        db.query(SystemSetting)
        .filter(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key.in_(BRANDING_KEYS),
        )
        .all()
    )
    stored = {row.key: row.value for row in rows}

    return {key: stored.get(key, DEFAULT_SETTINGS[key]) for key in BRANDING_KEYS}
