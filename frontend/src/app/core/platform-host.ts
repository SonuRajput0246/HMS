/**
 * Which hostnames serve the platform (super admin) console.
 *
 * The console is a second surface inside the same bundle: it is reached at a
 * reserved subdomain -- `platform.localhost:4200` in development,
 * `platform.example.com` in production -- and is never addressable from a
 * hotel's subdomain. Only the first DNS label is consulted, so both forms
 * behave identically.
 *
 * These labels are a subset of the backend's `RESERVED_SLUGS`
 * (`backend/src/api/middlewares/tenant_resolver.py`), which is what makes the
 * split possible: the backend refuses to create a hotel on any of them, so a
 * hotel can never claim the console's own host. The backend list is longer
 * because it also covers hosts the platform itself does not serve (`api`,
 * `www`, `static`, and so on); this one carries only the labels an operator
 * would actually reach the console on.
 *
 * Keep the two in step. A label added here and not there would be a route split
 * the API still refuses to resolve; a label added there and not here would be a
 * hotel that could shadow the console.
 */
export const PLATFORM_HOST_LABELS = ['platform', 'superadmin', 'console'];

/** True when `hostname` (defaulting to the current one) names the platform. */
export function isPlatformHost(hostname?: string): boolean {
  const host = (
    hostname ??
    (typeof window !== 'undefined' && window.location ? window.location.hostname : '')
  )
    .toLowerCase()
    .trim();

  if (!host) {
    return false;
  }

  // An IP literal (IPv4 "127.0.0.1", IPv6 "[::1]") is infrastructure, never a
  // labelled host, so it can never select the console. Checked before splitting
  // on "." because an IPv4 address's "first label" is not a DNS label at all.
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host) || host.includes(':') || host.includes('[')) {
    return false;
  }

  return PLATFORM_HOST_LABELS.includes(host.split('.')[0]);
}
