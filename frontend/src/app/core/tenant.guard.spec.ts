import { TestBed } from '@angular/core/testing';
import { UrlTree } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';

import { TenantGuard } from './tenant.guard';
import { TenantService } from '../services/tenant.service';

/**
 * The guard is the only thing between an unknown host and a rendered app, so
 * its three states are pinned here. The 404 route it points at is covered by
 * the route-table specs.
 */
describe('TenantGuard', () => {

  function guardFor(state: 'ok' | 'unknown' | 'no-tenant'): TenantGuard {
    TestBed.configureTestingModule({
      imports: [RouterTestingModule],
      providers: [{ provide: TenantService, useValue: { state } }],
    });
    return TestBed.inject(TenantGuard);
  }

  it('lets a resolved hotel through', () => {
    expect(guardFor('ok').canActivate()).toBe(true);
  });

  it('sends a host with no hotel to the 404 page', () => {
    const result = guardFor('no-tenant').canActivate();
    expect(result instanceof UrlTree).toBe(true);
    expect((result as UrlTree).toString()).toBe('/tenant-unavailable');
  });

  it('sends a host naming an unknown hotel to the 404 page', () => {
    const result = guardFor('unknown').canActivate();
    expect(result instanceof UrlTree).toBe(true);
    expect((result as UrlTree).toString()).toBe('/tenant-unavailable');
  });
});
