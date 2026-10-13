import { Injectable } from '@angular/core';

/**
 * Single source of truth for "where does this app live?".
 *
 * There is exactly one product here, so every getter is a constant. The service
 * exists rather than a bare string so that shared code -- the auth flow, the 404
 * page, the 403 page, the root redirect -- has one place to read the URL shape
 * from. If the route prefix ever moves, it moves here and nowhere else.
 *
 * Ordering matters: these are plain constants, so nothing has to be resolved
 * before first read, and nothing may depend on being initialised at all.
 *
 * Every navigation out of shared code should go through `homeUrl` rather than
 * spelling `/hms/...` out. Feature folders own their own internal paths and
 * can hardcode them.
 */
@Injectable({ providedIn: 'root' })
export class InstanceService {

  /** Human-readable product name, for chrome and welcome messages. */
  readonly label = 'HMS';

  /** URL segment the app is mounted under. */
  readonly prefix = 'hms';

  /** Landing URL after login. */
  readonly homeUrl = '/hms/dashboard';
}