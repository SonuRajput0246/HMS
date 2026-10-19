import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { isPlatformHost } from './platform-host';

/**
 * Route-level host split.
 *
 * Two surfaces share this bundle, so a path alone is not enough to pick a
 * route: `/auth/login` is the hotel sign-in on `demo.localhost:4200` and the
 * platform sign-in on `admin.localhost:4200`. `canMatch` is the right primitive
 * because it is evaluated before the router commits to a route and, crucially,
 * before a lazy module is fetched -- the hotel's chunks are never downloaded on
 * the platform host, and the reverse.
 *
 * The pair is exhaustive: one of the two always matches, so navigation never
 * dead-ends in the 404 route by accident.
 */

/** Matches only the platform host. */
export const platformHostMatch: CanMatchFn = () => isPlatformHost();

/**
 * Matches every host that is not the platform host -- i.e. the hotel app.
 *
 * On the platform host a hotel URL (`/hms/...`) is not a 404 but a redirect to
 * the console: the address is valid, just addressed to the wrong surface, and
 * sending the operator to the sign-in is more useful than "no such page".
 */
export const tenantHostMatch: CanMatchFn = () => {
  if (!isPlatformHost()) {
    return true;
  }
  return inject(Router).createUrlTree(['/platform/login']);
};
