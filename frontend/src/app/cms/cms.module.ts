import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { SharedModule } from '../shared/shared.module';
import { CmsRoutingModule } from './cms-routing.module';

import { CmsLayoutComponent } from './layout/cms-layout.component';
import { CmsSidenavComponent } from './layout/cms-sidenav.component';
import { CmsDashboardComponent } from './dashboard/cms-dashboard.component';
import { PosScreenComponent } from './pos/pos-screen.component';
import { KdsScreenComponent } from './kds/kds-screen.component';
import { TableListComponent } from './tables/table-list.component';
import { OrderListComponent, OrderDetailDialogComponent } from './orders/order-list.component';
import { CustomerListComponent, CustomerFormDialogComponent } from './customers/customer-list.component';
import { RecipeListComponent } from './recipes/recipe-list.component';
import { ReportScreenComponent } from './reports/report-screen.component';

/**
 * Cafe Management System feature module.
 *
 * Lazy-loaded from app-routing under /cms. Kept as one NgModule rather than a
 * folder of standalone components because that is what the rest of the codebase
 * does -- mixing the two styles in one app makes the module boundaries
 * ambiguous for whoever maintains it next.
 *
 * Everything is eagerly declared inside this module but lazily ROUTED, so the
 * whole CMS ships as one chunk behind /cms. Splitting into per-screen feature
 * modules would shave a little from the initial CMS load; at this size it is not
 * worth the extra indirection.
 */
@NgModule({
  declarations: [
    CmsLayoutComponent,
    CmsSidenavComponent,
    CmsDashboardComponent,
    PosScreenComponent,
    KdsScreenComponent,
    TableListComponent,
    OrderListComponent,
    CustomerListComponent,
    RecipeListComponent,
    ReportScreenComponent,
    // Dialogs are declared here rather than standalone: they are opened
    // programmatically from the list screens, so they must be compiled into
    // this module to resolve their Material / Forms dependencies.
    OrderDetailDialogComponent,
    CustomerFormDialogComponent
  ],
  imports: [
    CommonModule,
    SharedModule,
    CmsRoutingModule
  ]
})
export class CmsModule { }