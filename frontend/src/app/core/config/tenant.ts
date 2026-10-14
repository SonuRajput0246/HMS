/**
 * How the frontend knows which hotel it is serving.
 *
 * The tenant is part of the hostname, so it is known before any network call
 * and cannot be baked into a build artifact: the same bundle serves every
 * subdomain. `config.json` carries `api_base_url` and nothing about identity,
 * on purpose.
 *
 * The rule mirrors the backend's `_host_slug`
 * (`src/api/middlewares/tenant_resolver.py`), which is the authority. The
 * backend additionally knows its configured base domain and rejects a host
 * outside it; the browser cannot know that, so it applies the shape both agree
 * on: a bare host names no tenant, and a host with a subdomain names its first
 * label.
 */

/** Header the API reads when the tenant is not visible in its own Host header. */
export const TENANT_HEADER = 'X-Tenant';

/**
 * What the boot sequence learned about the host's tenant.
 *
 * `no-tenant` and `unknown` are both refusals -- the app shows the 404 page for
 * either, matching the API, which 404s a request that names no hotel. They are
 * kept apart because they mean different things to a developer reading a log:
 * one is a misconfigured address, the other names a hotel that does not exist.
 */
export type TenantState = 'ok' | 'unknown' | 'no-tenant';

/**
 * Hosts that name no tenant.
 *
 * `localhost` and the loopback addresses are the documented local-development
 * hosts for the *product*, not for a hotel; a hotel is reached at
 * `acme.localhost`, which is a different host. A single label with no dot can
 * only be such a host, so it is refused outright.
 *
 * An apex domain is not listed here because the browser cannot tell it apart
 * from a hotel subdomain -- `example.com` and `acme.example.com` are the same
 * shape without the base domain, which only the backend knows. `example.com`
 * therefore yields the label `example`, which names no hotel, and the app 404s
 * it as an unknown hotel rather than an unnamed one. The result is the same.
 */
const NON_TENANT_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);

/**
 * The tenant slug implied by `hostname`, or null when the host names none.
 *
 * Returns null rather than guessing "the first label" for a bare host: a stray
 * host must not silently select a hotel, for the same reason the backend does
 * not guess. See `_host_slug` for the server-side counterpart.
 */
export function tenantSlugFromHostname(hostname: string): string | null {
  const raw = (hostname || '').trim().toLowerCase();
  if (!raw || NON_TENANT_HOSTS.has(raw)) {
    return null;
  }

  /// `window.location.hostname` never carries the port, but this is also
  /// usable with a full host, so strip one when it is present.
  const host = raw.replace(/:\d+$/, '');
  if (NON_TENANT_HOSTS.has(host)) {
    return null;
  }

  const labels = host.split('.').filter(label => label.length > 0);
  if (labels.length < 2) {
    return null;
  }

  return labels[0];
}
