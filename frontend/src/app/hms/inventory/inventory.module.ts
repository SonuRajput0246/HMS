import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { InventoryRoutingModule } from './inventory-routing.module';
import { ListCategoryComponent } from './list-category/list-category.component';
import { ManageCategoryComponent } from './manage-category/manage-category.component';
import { ListInventoryComponent } from './list-inventory/list-inventory.component';
import { ManageInventoryComponent } from './manage-inventory/manage-inventory.component';
import { InventoryDashboardComponent } from './inventory-dashboard/inventory-dashboard.component';
import { SharedModule } from '../../shared/shared.module';


/**
 * Inventory screens.
 *
 * These live under `hms/` by history, not by dependency: every one of them
 * talks only to InventoryService and shared models, with no hotel-specific
 * code. The models, seeders and category/unit reference data all live in the
 * shared `common/` bucket, so moving the folder later is a routing change and
 * nothing else.
 *
 * The components are exported so a second route table can mount the same
 * screens under another prefix if the app ever grows one. They cannot simply
 * share this module's routing, because InventoryRoutingModule hardcodes
 * menuId 3, which is INVENTORY_MANAGEMENT -- a module id is not stable across
 * re-seeds, so a second mount would have to resolve its own.
 */
@NgModule({
  declarations: [
    ListCategoryComponent,
    ManageCategoryComponent,
    ListInventoryComponent,
    ManageInventoryComponent,
    InventoryDashboardComponent
  ],
  imports: [
    CommonModule,
    InventoryRoutingModule,
    SharedModule
  ],
  exports: [
    ListCategoryComponent,
    ManageCategoryComponent,
    ListInventoryComponent,
    ManageInventoryComponent,
    InventoryDashboardComponent
  ]
})
export class InventoryModule { }
