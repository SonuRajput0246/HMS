import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { PLATFORM_ACCESS_TOKEN_KEY } from './config/platform-storage';

/**
 * Gate for the console's authenticated shell.
 *
 * A missing token is not worth an error screen: the user is sent to the platform
 * sign-in with a `UrlTree`, so the router cancels the original navigation
 * instead of briefly rendering a shell that cannot load data.
 *
 * This checks only that a token is *present*, which is a routing convenience and
 * not an authorization decision. The real check is the server's: every endpoint
 * under `/api/v1/platform` runs `requires_super_admin`, so a stale, forged or
 * revoked token gets a 401 and the interceptor clears it and returns here.
 *
 * The key is the platform's own, never the tenant's, so one cannot stand in for
 * the other.
 */
export const platformAuthGuard: CanActivateFn = () => {
  const router = inject(Router);

  if (sessionStorage.getItem(PLATFORM_ACCESS_TOKEN_KEY)) {
    return true;
  }

  return router.createUrlTree(['/login']);
};
