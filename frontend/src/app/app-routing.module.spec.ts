import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, Routes, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { InstanceHomeRedirectComponent } from './core/instance-home-redirect.component';
import { routes as appRoutes } from './app-routing.module';
import { PageNotFoundComponent } from './shared/page-not-found/page-not-found.component';
import { UnauthorizedAccessComponent } from './shared/unauthorized-access/unauthorized-access.component';
import { platformHostMatch, tenantHostMatch } from './core/platform-host.guard';

/**
 * Covers the root redirect and the structural invariants of the real route
 * table, including the host split that keeps the platform console and the hotel
 * app from reaching each other.
 *
 * These tests use a stub feature route rather than the real hms table. The real
 * table pulls in a lazy module full of Material components and services that
 * need HttpClient, and rendering an actual dashboard would test the dashboard.
 * The redirect component is the part with logic in it; the route shapes are
 * covered by the structural tests below, which run against the real table.
 */
@Component({ selector: 'app-stub', standalone: true, template: 'stub' })
class StubDashboardComponent { }

@Component({ selector: 'app-stub-notfound', standalone: true, template: '404' })
class StubNotFoundComponent { }

describe('root routing', () => {

  /**
   * Stubs the real route shape: `hms` is a container with children, mirroring
   * the real module, which is `loadChildren` with its own child routes.
   *
   * The nesting matters. A bare leaf route (`path: 'hms'` + `loadComponent`)
   * cannot match `/hms/dashboard` at all -- it consumes only `hms` and leaves
   * `dashboard` unmatched, so it always falls through to `**`. Using a leaf
   * would make the assertions pass for the wrong reason.
   */
  function stubRoutes(): Routes {
    return [
      { path: '', pathMatch: 'full', component: InstanceHomeRedirectComponent },
      {
        path: 'hms',
        children: [{ path: 'dashboard', component: StubDashboardComponent }]
      },
      { path: '**', component: StubNotFoundComponent }
    ];
  }

  /**
   * The matched leaf route's path.
   *
   * Asserted instead of the activated component because a route using
   * loadComponent resolves its component asynchronously, and the router's
   * snapshot exposes it through a private field rather than `component`.
   */
  function matchedPath(): string | undefined {
    let route = TestBed.inject(Router).routerState.snapshot.root;
    while (route.firstChild) {
      route = route.firstChild;
    }
    return route.routeConfig?.path;
  }

  /** First-level path of the activated route, e.g. 'hms' or '**'. */
  function matchedRootPath(): string | undefined {
    return TestBed.inject(Router).routerState.snapshot.root.firstChild
      ?.routeConfig?.path;
  }

  function settle(): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, 0));
  }

  async function harness(): Promise<RouterTestingHarness> {
    TestBed.configureTestingModule({ providers: [provideRouter(stubRoutes())] });
    return RouterTestingHarness.create();
  }

  // ---- root redirect ----------------------------------------------------

  it('redirects / to /hms/dashboard', async () => {
    const h = await harness();
    // Start elsewhere first: re-navigating to the URL the router already holds
    // is a same-URL navigation, which the router ignores -- the redirect
    // component would never run and the assertion would pass vacuously.
    await h.navigateByUrl('/hms/dashboard');
    await h.navigateByUrl('/');
    await settle();

    expect(TestBed.inject(Router).url).toBe('/hms/dashboard');
  });

  it('replaces the URL rather than pushing, so Back leaves the app', async () => {
    const h = await harness();
    await h.navigateByUrl('/hms/dashboard');
    await h.navigateByUrl('/');
    await settle();

    // One entry in history, not two.
    expect(TestBed.inject(Router).navigated).toBe(true);
  });

  // ---- hms tree ---------------------------------------------------------

  it('matches a route under /hms', async () => {
    const h = await harness();
    await settle();
    await h.navigateByUrl('/hms/dashboard');
    await settle();

    expect(matchedRootPath()).toBe('hms');
    expect(matchedPath()).toBe('dashboard');
  });

  it('still 404s an unknown path', async () => {
    const h = await harness();
    await h.navigateByUrl('/hms/nope');
    await settle();

    expect(matchedRootPath()).toBe('**');
  });

  // ---- structural checks against the real table ------------------------

  it('the real table passes router validation', async () => {
    TestBed.configureTestingModule({ providers: [provideRouter(appRoutes)] });

    expect(() => TestBed.inject(Router).config).not.toThrow();
  });

  it('no real route lacks component, redirectTo, children or loadChildren', () => {
    // NG04014's exact precondition. This is the regression: the root route
    // once carried only a canActivate, which compiled cleanly and then threw
    // the moment the router validated its config at bootstrap.
    const invalid = appRoutes.filter(
      r => r.redirectTo === undefined
        && !r.component
        && !r.loadComponent
        && !r.children
        && !r.loadChildren
    );

    expect(invalid).toEqual([]);
  });

  it('no real route is both redirected and guarded', () => {
    const conflicted = appRoutes.filter(
      r => r.redirectTo && (r.canActivate?.length || r.canMatch?.length)
    );

    expect(conflicted).toEqual([]);
  });

  it('the real root route renders the redirect component', () => {
    // The redirect now lives inside the hotel shell, one level below the host
    // guard, so the route carrying it is `''` *with a tenant host* rather than
    // the top-level `''`. See the shell note in app-routing.module.ts.
    const tenantShell = appRoutes.find(
      r => r.path === '' && r.canMatch?.includes(tenantHostMatch)
    );
    expect(tenantShell?.children?.find(r => r.path === '')?.component)
      .toBe(InstanceHomeRedirectComponent);
  });

  it('the hotel tree mounts auth and hms lazily, and nothing else', () => {
    const tenantShell = appRoutes.find(
      r => r.path === '' && r.canMatch?.includes(tenantHostMatch)
    );
    const paths = (tenantShell?.children ?? []).map(r => r.path).sort();
    expect(paths).toEqual(['', 'auth', 'hms']);
    expect(tenantShell?.children?.find(r => r.path === 'auth')?.loadChildren)
      .toBeDefined();
    expect(tenantShell?.children?.find(r => r.path === 'hms')?.loadChildren)
      .toBeDefined();
  });

  it('the console is lazy-loaded behind the platform host guard', () => {
    // canMatch rather than canActivate, so the console's chunks are never
    // fetched on a hotel host -- which is the whole reason for the split.
    const platformShell = appRoutes.find(
      r => r.path === '' && r.canMatch?.includes(platformHostMatch)
    );
    // Mounted at the host's root: the console's URLs are `/login`,
    // `/dashboard`, ... with no `/platform` prefix.
    const mount = platformShell?.children?.find(r => r.loadChildren);
    expect(mount?.path).toBe('');
    expect(mount?.loadChildren).toBeDefined();
    expect(mount?.component).toBeUndefined();
  });

  it('exactly two host shells exist, and they are guarded, not redirected', () => {
    const shells = appRoutes.filter(r => r.path === '');
    expect(shells.length).toBe(2);
    expect(shells.every(r => r.canMatch?.length)).toBe(true);
    // A canMatch is not evaluated on a route carrying a redirectTo, so a
    // guarded shell must never be one.
    expect(shells.every(r => !r.redirectTo)).toBe(true);
  });

  it('the console host redirects the sign-in URLs an operator would try', () => {
    const platformShell = appRoutes.find(
      r => r.path === '' && r.canMatch?.includes(platformHostMatch)
    );
    const redirects = (platformShell?.children ?? [])
      .filter(r => r.redirectTo)
      .map(r => `${r.path} -> ${r.redirectTo}`);

    // The console's front door is the sign-in, not the dashboard, and the
    // redirects keep an operator's bookmark and hotel-app muscle memory working.
    expect(redirects).toContain(' -> login');
    expect(redirects).toContain('auth/login -> login');
    expect(redirects).toContain('auth -> login');
  });

  it('the 403 route is declared before the catch-all', () => {
    // A `**` route matches anything, so if it came first the 403 would render
    // the 404 page and "no permission" would be indistinguishable from
    // "no such page".
    const paths = appRoutes.map(r => r.path);
    expect(paths.indexOf('unauthorized-access'))
      .toBeLessThan(paths.indexOf('**'));
    expect(appRoutes.find(r => r.path === 'unauthorized-access')?.component)
      .toBe(UnauthorizedAccessComponent);
  });

  it('the real table still 404s unmatched URLs', () => {
    expect(appRoutes.find(r => r.path === '**')?.component)
      .toBe(PageNotFoundComponent);
  });

});