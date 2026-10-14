import { tenantSlugFromHostname } from './tenant';

/**
 * Browser storage keys.
 *
 * A session is a string in `sessionStorage` and a JSON blob in `localStorage`,
 * and the same names are read from more than one place (the auth guard, the
 * refresh interceptor, and the post-login flow), so a typo in one of them
 * silently drops the session rather than failing loudly.
 *
 * Each key now also carries the tenant slug, because a session belongs to the
 * hotel that created it. Storage is already partitioned by origin, so two
 * hotels on two subdomains do not collide today -- but the app can also be
 * served from a single origin, and a key that ignores the tenant turns that
 * into one hotel quietly reading the other's token.
 */

/**
 * The storage keys for a given tenant.
 *
 * Pure and exported so the rule can be tested directly; `STORAGE_KEYS` is this
 * function applied to the host the document was loaded from. The slug cannot
 * change without a reload, so resolving it once is enough and no reader has to
 * pass it in.
 */
export function scopedStorageKeys(slug: string | null): {
  ACCESS_TOKEN: string;
  USER_DATA: string;
} {
  const suffix = slug ? `_${slug}` : '';
  return {
    ACCESS_TOKEN: `app_accessToken${suffix}`,
    USER_DATA: `app_userData${suffix}`,
  };
}

export const STORAGE_KEYS = scopedStorageKeys(
  tenantSlugFromHostname(window.location.hostname)
);
