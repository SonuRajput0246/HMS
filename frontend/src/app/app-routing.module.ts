import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { PageNotFoundComponent } from './shared/page-not-found/page-not-found.component';
import { InstanceHomeRedirectComponent } from './core/instance-home-redirect.component';
import { UnauthorizedAccessComponent } from './shared/unauthorized-access/unauthorized-access.component';
import { TenantGuard } from './core/tenant.guard';
import { platformHostMatch, tenantHostMatch } from './core/platform-host.guard';

/**
 * The route table, split by host into two surfaces.
 *
 * One bundle serves both the hotel app and the platform (super admin) console,
 * and the two must never be reachable from each other. Which one a visitor gets
 * is decided by the host: `platform.localhost:4200` is the console, every other
 * host is a hotel.
 *
 * Each surface is a single component-less "shell" route carrying a `canMatch`
 * host guard, with everything that surface can do as its children.
 *
 * The shell exists because of a router constraint worth remembering:
 * **`canMatch` is not evaluated on a route that has `redirectTo`.** Matching a
 * redirect stops at `processSegmentAgainstRoute`, which branches to
 * `expandSegmentAgainstRouteUsingRedirect` before `matchWithChecks` (and so
 * before `runCanMatchGuards`) ever runs. A gated redirect therefore redirects on
 * every host, which is precisely the bug this shape avoids: the shell is a
 * normal (non-redirect) route, so its guard does run, and the redirects live one
 * level below where the host has already been decided.
 *
 * `canMatch` rather than `canActivate` is deliberate: it is consulted before a
 * lazy module is fetched, so the console's chunks are never downloaded on a
 * hotel host and the hotel's never are on the console host. It is also what lets
 * `/auth/login` mean two different things, since the path alone cannot tell the
 * two surfaces apart.
 */
export const routes: Routes = [
  // ---- Platform console: only on the console host. ----
  {
    path: '',
    canMatch: [platformHostMatch],
    children: [
      {
        // The console's front door. `/` is the sign-in, not a dashboard, so a
        // visitor is never sent through an authenticated shell first.
        path: '',
        pathMatch: 'full',
        redirectTo: 'login'
      },
      {
        // The URLs an operator reaches for out of habit, and old bookmarks.
        path: 'auth/login',
        redirectTo: 'login'
      },
      {
        path: 'auth',
        pathMatch: 'full',
        redirectTo: 'login'
      },
      {
        // Mounted at the console host's root, so the surface owns `/login`,
        // `/dashboard`, `/tenants`, ... rather than living under `/platform`.
        path: '',
        loadChildren: () => import('./platform/platform.module').then(a => a.PlatformModule)
      }
    ]
  },

  // ---- Hotel app: every other host. ----
  {
    path: '',
    canMatch: [tenantHostMatch],
    children: [
      {
        path: '',
        pathMatch: 'full',
        component: InstanceHomeRedirectComponent,
        canActivate: [TenantGuard]
      },
      {
        path: 'auth',
        loadChildren: () => import('./auth/auth.module').then(a => a.AuthModule),
        canActivate: [TenantGuard]
      },
      {
        path: 'hms',
        loadChildren: () => import('./hms/hms.module').then(a => a.HmsModule),
        canActivate: [TenantGuard]
      }
    ]
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
