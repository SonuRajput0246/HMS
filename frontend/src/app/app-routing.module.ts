import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { PageNotFoundComponent } from './shared/page-not-found/page-not-found.component';
import { InstanceHomeRedirectComponent } from './core/instance-home-redirect.component';
import { UnauthorizedAccessComponent } from './shared/unauthorized-access/unauthorized-access.component';
import { TenantGuard } from './core/tenant.guard';

/**
 * The route table is a plain static array.
 *
 * `RouterModule.forRoot(buildAppRoutes(inject(...)))` is not an option:
 * NgModule metadata is evaluated outside any injection context, so inject()
 * has nothing to inject from (NG0203). That is also why the root redirect is a
 * component rather than a `redirectTo` string -- `redirectTo` only accepts a
 * static string, and the landing URL comes from InstanceService. See
 * InstanceHomeRedirectComponent.
 *
 * Every route a visitor can land on carries TenantGuard, which sends a host
 * that does not name a usable hotel to the 404 page. The catch-all and the 403
 * page are deliberately left unguarded: both are reachable whatever the tenant
 * and neither leads anywhere that needs one.
 */
export const routes: Routes = [
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