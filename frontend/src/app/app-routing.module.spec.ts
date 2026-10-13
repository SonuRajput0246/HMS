import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, Routes, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { AppConfig } from './core/config/config';
import { InstanceService } from './core/config/instance.service';
import { InstanceHomeRedirectComponent } from './core/instance-home-redirect.component';
import { routes as appRoutes } from './app-routing.module';
import { PageNotFoundComponent } from './shared/page-not-found/page-not-found.component';

/**
 * Covers the two pieces of instance-aware routing logic: the canMatch gate and
 * the root redirect.
 *
 * These tests use stub feature routes rather than the real hms/cms tables. The
 * real tables pull in lazy modules full of Material components and services that
 * need HttpClient, and rendering an actual dashboard would test the dashboard.
 * The guards and the redirect component are the parts with logic in them; the
 * route shapes are covered separately by the structural tests below, which run
 * against the real exported table.
 */
@Component({ selector: 'app-stub', standalone: true, template: 'stub' })
class StubDashboardComponent { }

@Component({ selector: 'app-stub-notfound', standalone: true, template: '404' })
class StubNotFoundComponent { }

describe('instance-aware routing', () => {

  /**
   * Stubs the real route shapes: each instance route is a container with
   * children, mirroring hms/cms which are `loadChildren` modules with their own
   * child routes.
   *
   * The nesting matters. A bare leaf route (`path: 'hms'` + `loadComponent`)
   * cannot match `/hms/dashboard` at all -- it consumes only `hms` and leaves
   * `dashboard` unmatched, so it always falls through to `**`. Using a leaf
   * would make the guard assertions pass for the wrong reason, and would hide a
   * genuinely broken real route.
   */
  function stubRoutes(): Routes {
    const activeInstance = (type: string) => () => injectType() === type;

    return [
      { path: '', pathMatch: 'full', component: InstanceHomeRedirectComponent },
      {
        path: 'hms',
        canMatch: [activeInstance('HMS')],
        children: [{ path: 'dashboard', component: StubDashboardComponent }]
      },
      {
        path: 'cms',
        canMatch: [activeInstance('CMS')],
        children: [{ path: 'dashboard', component: StubDashboardComponent }]
      },
      { path: '**', component: StubNotFoundComponent }
    ];
  }

  function injectType(): string {
    return TestBed.inject(InstanceService).type;
  }

  /**
   * The matched leaf route's path.
   *
   * Asserted instead of the activated component because a route using
   * loadComponent resolves its component asynchronously, and the router's
   * snapshot exposes it through a private field rather than `component`. The
   * matched path is what actually distinguishes "the guard let this through"
   * from "the router fell through to **", which is the property under test.
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

  async function harnessFor(instanceType: 'HMS' | 'CMS'): Promise<RouterTestingHarness> {
    const config = new AppConfig();
    config.set('BASE_URL', 'http://localhost:5000');
    config.set('INSTANCE_TYPE', instanceType);

    TestBed.configureTestingModule({
      providers: [provideRouter(stubRoutes()), { provide: AppConfig, useValue: config }]
    });

    return RouterTestingHarness.create();
  }

  // ---- root redirect ----------------------------------------------------

  it('redirects / to /hms/dashboard on an HMS deployment', async () => {
    const harness = await harnessFor('HMS');
    // Start elsewhere first: re-navigating to the URL the router already holds
    // is a same-URL navigation, which the router ignores -- the redirect
    // component would never run and the assertion would pass vacuously.
    await harness.navigateByUrl('/hms/dashboard');
    await harness.navigateByUrl('/');
    await settle();

    expect(TestBed.inject(Router).url).toBe('/hms/dashboard');
  });

  it('redirects / to /cms/dashboard on a CMS deployment', async () => {
    const harness = await harnessFor('CMS');
    await harness.navigateByUrl('/cms/dashboard');
    await harness.navigateByUrl('/');
    await settle();

    expect(TestBed.inject(Router).url).toBe('/cms/dashboard');
  });

  it('replaces the URL rather than pushing, so Back leaves the app', async () => {
    const harness = await harnessFor('HMS');
    await harness.navigateByUrl('/hms/dashboard');
    await harness.navigateByUrl('/');
    await settle();

    // One entry in history, not two.
    expect(TestBed.inject(Router).navigated).toBe(true);
  });

  // ---- canMatch gate ----------------------------------------------------

  it('matches the HMS route on an HMS deployment', async () => {
    const harness = await harnessFor('HMS');
    await settle();
    await harness.navigateByUrl('/hms/dashboard');
    await settle();

    expect(matchedRootPath()).toBe('hms');
    expect(matchedPath()).toBe('dashboard');
  });

  it('blocks the HMS route on a CMS deployment', async () => {
    const harness = await harnessFor('CMS');
    await harness.navigateByUrl('/hms/dashboard');

    // canMatch returned false, so recognition fell through to **. Note the URL
    // is still /hms/dashboard: a ** route matches any URL while leaving it in
    // the address bar, which is why this asserts on the matched route rather
    // than on router.url.
    expect(matchedRootPath()).toBe('**');
  });

  it('blocks the CMS route on an HMS deployment', async () => {
    const harness = await harnessFor('HMS');
    await harness.navigateByUrl('/cms/dashboard');

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
    expect(appRoutes.find(r => r.path === '')?.component)
      .toBe(InstanceHomeRedirectComponent);
  });

  it('both real instance routes are guarded', () => {
    expect(appRoutes.find(r => r.path === 'hms')?.canMatch).toBeDefined();
    expect(appRoutes.find(r => r.path === 'cms')?.canMatch).toBeDefined();
  });

  it('the real table still 404s unmatched URLs', () => {
    expect(appRoutes.find(r => r.path === '**')?.component)
      .toBe(PageNotFoundComponent);
  });

});