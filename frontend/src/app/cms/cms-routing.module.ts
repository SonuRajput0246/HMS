import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AuthGuard } from '../core/auth.guard';
import { CmsLayoutComponent } from './layout/cms-layout.component';
import { CmsDashboardComponent } from './dashboard/cms-dashboard.component';
import { PosScreenComponent } from './pos/pos-screen.component';
import { KdsScreenComponent } from './kds/kds-screen.component';
import { TableListComponent } from './tables/table-list.component';
import { OrderListComponent } from './orders/order-list.component';
import { CustomerListComponent } from './customers/customer-list.component';
import { RecipeListComponent } from './recipes/recipe-list.component';
import { ReportScreenComponent } from './reports/report-screen.component';

/**
 * CMS routes.
 *
 * `menuId` values are the module ids from the CMS module seeder
 * (src/database/seeders/cms/module_seeder.py). AuthGuard reads them off
 * route.data and checks the signed-in user's menu_access, so a role without
 * TABLE access cannot reach /cms/tables even by typing the URL.
 *
 * Two of these were wrong and are fixed here:
 *
 *  - `reports` used menuId 1 (DASHBOARD) because no REPORTS module existed.
 *    That handed sales and customer data to anyone with dashboard access. It
 *    is now its own module (id 16), granted to MANAGER/ADMIN/SUPER_ADMIN only.
 *  - `recipes` used menuId 12 (RECIPE_ITEM), the child list rather than
 *    RECIPE (11), the parent menu. Same access outcome here, wrong level.
 *
 * ## Shell
 *
 * Most screens sit under CmsLayoutComponent, which supplies the sidebar and
 * title bar. POS and KDS are deliberately outside it: both are full-bleed
 * screens that a cashier and a chef use continuously, and the sidebar and
 * breadcrumb would eat vertical space they need. They carry their own back
 * links for the same reason -- a full-bleed screen with no way out is a trap
 * the browser back button should not be the only answer to.
 *
 * Both groups still carry AuthGuard. The shell is presentation, not a security
 * boundary; each child route is gated on its own module so a role holding
 * TABLE can open the shell without thereby gaining ORDERS.
 */
export const routes: Routes = [
  // ---- full-bleed operational screens, no shell chrome -----------------
  {
    path: 'pos',
    component: PosScreenComponent,
    canActivate: [AuthGuard],
    data: { menuId: 7, breadcrumb: 'POS / Billing' }
  },
  {
    path: 'kds',
    component: KdsScreenComponent,
    canActivate: [AuthGuard],
    data: { menuId: 6, breadcrumb: 'Kitchen Display' }
  },

  // ---- everything else, inside the shell --------------------------------
  {
    path: '',
    component: CmsLayoutComponent,
    canActivate: [AuthGuard],
    children: [
      {
        path: 'dashboard',
        component: CmsDashboardComponent,
        canActivate: [AuthGuard],
        data: { menuId: 1, breadcrumb: 'Dashboard' }
      },
      {
        path: 'tables',
        component: TableListComponent,
        canActivate: [AuthGuard],
        data: { menuId: 3, breadcrumb: 'Table Management' }
      },
      {
        path: 'orders',
        component: OrderListComponent,
        canActivate: [AuthGuard],
        data: { menuId: 4, breadcrumb: 'Order Management' }
      },
      {
        path: 'customers',
        component: CustomerListComponent,
        canActivate: [AuthGuard],
        data: { menuId: 5, breadcrumb: 'Customer Management' }
      },
      {
        path: 'recipes',
        component: RecipeListComponent,
        canActivate: [AuthGuard],
        data: { menuId: 11, breadcrumb: 'Menu & Recipes' }
      },
      {
        // Shared inventory screens, mounted on the CMS module ids. See
        // cms/inventory/cms-inventory-routing.module.ts for why the route table
        // is duplicated rather than reused from hms/.
        path: 'inventory',
        loadChildren: () =>
          import('./inventory/cms-inventory.module').then(m => m.CmsInventoryModule),
        canActivate: [AuthGuard],
        data: { menuId: 8, breadcrumb: 'Inventory Management' }
      },
      {
        path: 'reports',
        component: ReportScreenComponent,
        canActivate: [AuthGuard],
        data: { menuId: 16, breadcrumb: 'Reports' }
      },

      // Landing for /cms once the shell is up.
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' }
    ]
  }
];

/**
 * Exported so cms-menu.spec.ts can assert that every registry entry points at
 * a path this table actually serves. The registry and the route table are kept
 * in step by hand otherwise, which is how a menu link starts 404ing again.
 */
@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class CmsRoutingModule { }