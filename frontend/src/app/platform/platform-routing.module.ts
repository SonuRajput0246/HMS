import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { platformAuthGuard } from '../core/platform-auth.guard';
import { PlatformLoginComponent } from './login/login.component';
import { PlatformLayoutComponent } from './layout/layout.component';
import { PlatformDashboardComponent } from './dashboard/dashboard.component';
import { PlatformActivityComponent } from './activity/activity.component';
import { AdminListComponent } from './admins/list/list.component';
import { ManageAdminComponent } from './admins/manage-admin/manage-admin.component';
import { PlatformSecurityComponent } from './security/security.component';
import { TenantListComponent } from './tenants/list/list.component';
import { ManageTenantComponent } from './tenants/manage-tenant/manage-tenant.component';

/**
 * Console routes. The whole module is only reachable on the platform host --
 * `app-routing.module.ts` gates the lazy load with `platformHostMatch` -- so
 * nothing here repeats that check.
 *
 * The module is mounted at the host's root, so these paths are the console's
 * public URLs: `/login`, `/dashboard`, `/tenants`, and so on. There is no
 * `/platform` segment in front of them.
 *
 * `login` is a sibling of the shell rather than a child: signing in must not
 * render the toolbar, and the shell's `canActivate` would bounce a
 * token-less visitor back to this very route.
 */
const routes: Routes = [
  {
    path: 'login',
    component: PlatformLoginComponent,
  },
  {
    path: '',
    component: PlatformLayoutComponent,
    canActivate: [platformAuthGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        component: PlatformDashboardComponent,
      },
      {
        path: 'tenants',
        component: TenantListComponent,
      },
      {
        // `new` is declared before `:id/edit` so it is never read as an id.
        path: 'tenants/new',
        component: ManageTenantComponent,
      },
      {
        path: 'tenants/:id/edit',
        component: ManageTenantComponent,
      },
      {
        path: 'activity',
        component: PlatformActivityComponent,
      },
      {
        path: 'admins',
        component: AdminListComponent,
      },
      {
        // `new` is declared before `:id/edit` so it is never read as an id.
        path: 'admins/new',
        component: ManageAdminComponent,
      },
      {
        path: 'admins/:id/edit',
        component: ManageAdminComponent,
      },
      {
        path: 'security',
        component: PlatformSecurityComponent,
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class PlatformRoutingModule {}
