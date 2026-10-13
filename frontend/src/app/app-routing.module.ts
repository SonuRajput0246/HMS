import { inject, NgModule } from '@angular/core';
import { CanMatchFn, RouterModule, Routes } from '@angular/router';
import { PageNotFoundComponent } from './shared/page-not-found/page-not-found.component';
import { InstanceHomeRedirectComponent } from './core/instance-home-redirect.component';
import { UnauthorizedAccessComponent } from './shared/unauthorized-access/unauthorized-access.component';
import { InstanceService } from './core/config/instance.service';

/**
 * Guards `/hms` or `/cms` so only the active instance's module can match.
 *
 * `canMatch` is used deliberately rather than `canActivate`: it is the only one
 * of the two that runs BEFORE `loadChildren` fetches the lazy chunk, so a CMS
 * deployment never downloads the hotel screens even if someone types the URL.
 * A `canActivate` guard would still fire the download during recognition.
 *
 * Both routes are declared unconditionally; returning false makes the router
 * fall through to the `**` route, so a stale bookmark lands on the 404 page,
 * which then offers a link home.
 */
function activeInstance(...types: string[]): CanMatchFn {
  return () => types.includes(inject(InstanceService).type);
}

/**
 * The route table is a plain static array. Both instance routes are declared
 * unconditionally and `canMatch` decides which one is reachable, so nothing
 * here needs to know the instance type at module-evaluation time.
 *
 * Two things rule out the alternatives:
 *
 *  - `RouterModule.forRoot(buildAppRoutes(inject(...)))` throws NG0203. NgModule
 *    metadata is evaluated outside any injection context, so inject() has
 *    nothing to inject from.
 *
 *  - Passing a factory to forRoot() avoids NG0203 but is a timing trap. The
 *    Router constructor resolves ROUTES eagerly, and the Router is constructed
 *    the first time HttpClient sends a request -- which is InitialService
 *    fetching config.json. The factory would therefore run before the instance
 *    type was read and bake in the HMS default every time.
 *
 * `canMatch` sidesteps both: it is evaluated during navigation, long after
 * startup, so it always sees a loaded config.
 */
export const routes: Routes = [
  {
    // `redirectTo` only accepts a static string, so an instance-aware redirect
    // needs a component. See InstanceHomeRedirectComponent.
    path: '',
    pathMatch: 'full',
    component: InstanceHomeRedirectComponent
  },
  {
    path: 'auth',
    loadChildren: () => import('./auth/auth.module').then(a => a.AuthModule)
  },
  {
    path: 'hms',
    canMatch: [activeInstance('HMS')],
    loadChildren: () => import('./hms/hms.module').then(a => a.HmsModule)
  },
  {
    path: 'cms',
    canMatch: [activeInstance('CMS')],
    loadChildren: () => import('./cms/cms.module').then(a => a.CmsModule)
  },
  {
    // AuthGuard sends denied users here. Declared before `**` because a `**`
    // route matches anything; without this the 403 fell through to the 404
    // page and "no permission" was indistinguishable from "no such page".
    path: 'unauthorized-access',
    component: UnauthorizedAccessComponent
  },
  {
    path: '**',
    component: PageNotFoundComponent
  }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }