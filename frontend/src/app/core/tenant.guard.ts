import { inject, Injectable } from '@angular/core';
import { Router, UrlTree } from '@angular/router';
import { TenantService } from '../services/tenant.service';

/**
 * Refuses the app on a host that does not name a usable hotel.
 *
 * This mirrors the API, which answers 404 both for a request that names no
 * tenant and for one that names a hotel that does not exist. Sending those to
 * the same 404 page the unmatched-URL catch-all uses is deliberate: to a
 * visitor there is no useful difference between "this address is not a hotel"
 * and "this page does not exist".
 *
 * Applied to the three entry routes rather than to a wrapper parent route, so
 * the flat route table stays flat.
 */
@Injectable({ providedIn: 'root' })
export class TenantGuard {

  private tenant = inject(TenantService);
  private router = inject(Router);

  canActivate(): boolean | UrlTree {
    if (this.tenant.state === 'ok') {
      return true;
    }

    /// An unmatched path renders the 404 page and is not itself guarded, so
    /// this cannot loop.
    return this.router.parseUrl('/tenant-unavailable');
  }
}
