from src.api.models.tenant_model import Tenant
from src.api.utils.responses import service_response
from src.api.utils.tenant_settings import get_tenant_branding


class TenantService:

    def __init__(self, db):
        self.db = db


    def find_by_slug(self, slug: str | None):
        """The live tenant for a slug, or None.

        A soft-deleted tenant is treated as absent, not as found: a deleted
        hotel's subdomain has to stop resolving rather than keep serving its
        data. Matching on is_deleted rather than only id is what makes that
        true.
        """
        if not slug:
            return None

        return (
            self.db.query(Tenant)
            .filter(
                Tenant.slug == slug,
                Tenant.is_deleted == False,
            )
            .first()
        )


    def get_public_info(self, tenant):
        """The part of a tenant that is safe to serve without a token.

        Deliberately narrow. The login page needs the hotel's name and branding
        so a user can see they are at the right address; nothing else about a
        tenant is anonymous business. No id, no provisioning state, no flags --
        any of those would let an unauthenticated caller enumerate the platform.

        The `branding` block is the hotel's own `system_settings` subset (see
        `tenant_settings`), which is what makes a login page -- and the mail it
        triggers -- belong to the hotel rather than to the product.
        """
        if tenant is None:
            return service_response(
                False,
                "No tenant is associated with this request.",
                None,
                404,
            )

        branding = get_tenant_branding(self.db, tenant.id)

        return service_response(
            True,
            "Tenant resolved.",
            {
                "slug": tenant.slug,
                "name": tenant.name,
                "branding": {
                    ## The hotel's chosen name, as opposed to the registry
                    ## `name` above, which is the platform admin's label for it.
                    "display_name": branding["company_name"],
                    "app_logo_image": branding["app_logo_image"],
                    "terms_condition_url": branding["terms_condition_url"],
                    "privacy_policy_url": branding["privacy_policy_url"],
                },
            },
            200,
        )
