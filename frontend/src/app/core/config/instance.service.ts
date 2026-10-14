import { Injectable } from '@angular/core';
import { tenantSlugFromHostname } from './tenant';

/**
 * Single source of truth for "where does this app live, and for whom?".
 *
 * `slug`, `prefix` and `homeUrl` are plain constants: nothing has to be
 * resolved before first read, and nothing may depend on being initialised at
 * all. Only `label` is filled later, by the boot sequence, and it is safe to
 * read before then because it starts at a real value rather than empty.
 *
 * Every navigation out of shared code should go through `homeUrl` rather than
 * spelling `/hms/...` out. Feature folders own their own internal paths and
 * can hardcode them.
 */
@Injectable({ providedIn: 'root' })
export class InstanceService {

  /**
   * The hotel this deployment serves, taken from the subdomain.
   *
   * Resolved once, at construction: the host cannot change without a reload, so
   * there is nothing to keep in sync. `null` on a host that names no tenant --
   * `localhost`, an IP -- which the app treats as a 404, matching the API,
   * rather than guessing which hotel was meant. An apex domain is not null; it
   * yields a label that names no hotel and 404s the same way. See `tenant.ts`.
   */
  readonly slug = tenantSlugFromHostname(window.location.hostname);

  /** Whether the host names a hotel at all. */
  readonly hasTenant = this.slug !== null;

  /**
   * Human-readable hotel name, for chrome and welcome messages.
   *
   * Seeded with the product name so it is never empty before boot finishes;
   * `TenantService` replaces it with the hotel's own name once the public
   * `tenant-info` call answers. That name is the hotel's `company_name`, not
   * the registry label the platform admin sees -- see `tenant_settings`.
   */
  label = 'HMS';

  /** URL segment the app is mounted under. */
  readonly prefix = 'hms';

  /** Landing URL after login. */
  readonly homeUrl = '/hms/dashboard';
}
